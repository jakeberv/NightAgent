import asyncio
import json

import joblib
import numpy as np
import pytest

from tests.test_problem import profile


def test_generic_regression_worker_metrics_and_hidden_dedup(tmp_path):
    from study.problem import ProblemSpec, assert_problem_matches
    from study.science import prepare_dataset, run_trial, evaluate_selected, project_info
    from study.tasks import get_adapter
    problem = ProblemSpec.from_dict(profile('tabular_regression', 'rmse'))
    data = tmp_path / 'data'
    manifest = prepare_dataset(data, problem=problem)
    assert manifest['problem_hash'] == problem.fingerprint
    assert_problem_matches(data, problem)
    adapter = get_adapter(problem)
    assert adapter.reference_config['model'] == 'ridge'
    result = asyncio.run(run_trial(data, tmp_path / 'trial', adapter.reference_config, seed=9, timeout=20))
    assert result['status'] == 'completed', result
    assert result['score'] == result['metrics']['rmse']
    assert result['score'] > 0
    assert 'validation_auc' not in result
    info = project_info(data)
    assert 'test' not in info['counts']
    evaluated = evaluate_selected(data, tmp_path / 'run', {'best': result, 'useful': result})
    assert evaluated['best'] == evaluated['useful']
    assert evaluated['best']['score'] == evaluated['best']['metrics']['rmse']
    (data / 'test.npz').unlink()
    assert evaluate_selected(data, tmp_path / 'run', {'best': result})['best'] == evaluated['best']


def test_npz_official_test_and_image_flattening_preserve_partition(tmp_path):
    from study.problem import ProblemSpec
    from study.science import prepare_dataset
    value = profile()
    value['dataset'] = {'format': 'npz', 'path': str(tmp_path / 'mnist.npz'), 'feature_array': 'x_train', 'target_array': 'y_train', 'test_feature_array': 'x_test', 'test_target_array': 'y_test', 'flatten': True}
    value['evaluation']['split'] = {'train': .8, 'validation': .2, 'test': 'official', 'seed': 3}
    X = np.arange(120*2*2).reshape(120, 2, 2)
    y = np.tile(np.arange(3), 40)
    np.savez(tmp_path / 'mnist.npz', x_train=X, y_train=y, x_test=np.ones((30, 2, 2))*9999, y_test=np.tile(np.arange(3), 10))
    manifest = prepare_dataset(tmp_path / 'data', problem=ProblemSpec.from_dict(value))
    assert manifest['partitions']['test']['rows'] == 30
    with np.load(tmp_path / 'data/test.npz') as test, np.load(tmp_path / 'data/train.npz') as train:
        assert test['X'].shape == (30, 4)
        assert test['X'].min() == 9999
        assert train['X'].max() < 9999
        assert not set(test['row_ids']) & set(train['row_ids'])


def test_csv_numeric_features_and_arbitrary_labels(tmp_path):
    from study.problem import ProblemSpec, assert_problem_matches
    from study.science import prepare_dataset
    value = profile()
    path = tmp_path / 'labels.csv'
    path.write_text('x,ignore,target\n' + '\n'.join(f'{i},not-numeric,{["red", "green", "blue"][i%3]}' for i in range(120)))
    value['dataset'] = {'format': 'csv', 'path': str(path), 'header': True, 'target_column': 'target', 'exclude_columns': ['ignore']}
    spec = ProblemSpec.from_dict(value)
    data = tmp_path / 'data'
    manifest = prepare_dataset(data, problem=spec)
    assert manifest['feature_names'] == ['x']
    with np.load(data / 'train.npz') as train:
        assert set(train['y']) == {'red', 'green', 'blue'}
    value['brief'] += ' changed'
    with pytest.raises(ValueError, match='problem'):
        assert_problem_matches(data, ProblemSpec.from_dict(value))
    (data / 'train.npz').chmod(0o644)
    (data / 'train.npz').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='fingerprint|hash'):
        assert_problem_matches(data, spec)


def test_multiclass_metrics_and_train_only_scale(tmp_path):
    from study.problem import ProblemSpec
    from study.science import prepare_dataset, run_trial
    value = profile()
    value['evaluation']['additional_metrics'] = ['macro_f1']
    spec = ProblemSpec.from_dict(value)
    data = tmp_path / 'data'
    prepare_dataset(data, problem=spec)
    (data / 'test.npz').unlink()
    config = {'model': 'logistic', 'preprocessing': 'standard', 'params': {}}
    result = asyncio.run(run_trial(data, tmp_path / 'trial', config, seed=7, timeout=20))
    assert result['status'] == 'completed', result
    assert set(result['metrics']) == {'accuracy', 'macro_f1'}
    pipeline = joblib.load(result['artifact'])['pipeline']
    with np.load(data / 'train.npz') as train:
        np.testing.assert_allclose(pipeline.named_steps['scale'].mean_, train['X'].mean(axis=0))


@pytest.mark.parametrize('kind', ['nan', 'object', 'image_without_flatten', 'unknown_class'])
def test_npz_rejects_invalid_arrays_before_fitting(tmp_path, kind):
    from study.problem import ProblemSpec
    from study.science import prepare_dataset
    value = profile()
    value['dataset'] = {'format': 'npz', 'path': str(tmp_path / 'arrays.npz'), 'feature_array': 'features', 'target_array': 'labels'}
    X, y = np.ones((120, 4)), np.tile(np.arange(3), 40)
    if kind == 'nan': X[0, 0] = np.nan
    elif kind == 'object': X = np.asarray([['unsafe']*4]*120, dtype=object)
    elif kind == 'image_without_flatten': X = X.reshape(120, 2, 2)
    elif kind == 'unknown_class':
        value['dataset'].update(test_feature_array='test_features', test_target_array='test_labels')
        value['evaluation']['split'] = {'train': .8, 'validation': .2, 'test': 'official'}
    np.savez(tmp_path / 'arrays.npz', features=X, labels=y, test_features=np.ones((30, 4)), test_labels=np.repeat(9, 30))
    with pytest.raises(ValueError):
        prepare_dataset(tmp_path / 'data', problem=ProblemSpec.from_dict(value))
    assert not (tmp_path / 'data/train.npz').exists()


def test_binary_auc_uses_explicit_positive_column(tmp_path):
    from sklearn.metrics import roc_auc_score
    from study.problem import ProblemSpec
    from study.science import prepare_dataset, run_trial
    value = profile(metric='roc_auc')
    value['dataset'].update(n_classes=2, positive_class=0)
    data = tmp_path / 'data'
    spec = ProblemSpec.from_dict(value)
    prepare_dataset(data, problem=spec)
    result = asyncio.run(run_trial(data, tmp_path / 'trial', {'model': 'logistic', 'preprocessing': 'standard', 'params': {}}, seed=9, timeout=20))
    assert result['status'] == 'completed', result
    pipeline = joblib.load(result['artifact'])['pipeline']
    with np.load(data / 'validation.npz') as validation:
        expected = roc_auc_score(validation['y'] == 0, pipeline.predict_proba(validation['X'])[:, 0])
    assert result['score'] == result['validation_auc'] == result['metrics']['roc_auc'] == expected


def test_generic_worker_receives_no_original_source_or_test_arrays(tmp_path, monkeypatch):
    from study.problem import ProblemSpec
    from study.science import prepare_dataset, run_trial
    value = profile()
    source = tmp_path / 'private-source.npz'
    np.savez(source, pixels=np.arange(480).reshape(120, 4), labels=np.tile(np.arange(3), 40), SECRET_TEST_PIXELS=np.ones((30, 4)), SECRET_TEST_LABELS=np.tile(np.arange(3), 10))
    value['dataset'] = {'format': 'npz', 'path': str(source), 'feature_array': 'pixels', 'target_array': 'labels', 'test_feature_array': 'SECRET_TEST_PIXELS', 'test_target_array': 'SECRET_TEST_LABELS'}
    value['evaluation']['split'] = {'train': .8, 'validation': .2, 'test': 'official'}
    data = tmp_path / 'data'
    prepare_dataset(data, problem=ProblemSpec.from_dict(value))
    real_spawn = asyncio.create_subprocess_exec
    captured = {}
    async def capture_spawn(*args, **kwargs):
        process = await real_spawn(*args, **kwargs)
        communicate = process.communicate
        async def capture_request(raw):
            captured['raw'] = raw.decode()
            return await communicate(raw)
        process.communicate = capture_request
        return process
    monkeypatch.setattr(asyncio, 'create_subprocess_exec', capture_spawn)
    result = asyncio.run(run_trial(data, tmp_path / 'trial', {'model': 'logistic', 'preprocessing': 'standard', 'params': {}}, seed=9, timeout=20))
    assert result['status'] == 'completed', result
    assert str(source) not in captured['raw']
    assert 'SECRET_TEST' not in captured['raw']
    assert 'test.npz' not in captured['raw']


@pytest.mark.parametrize('model', ['ridge', 'random_forest', 'histogram_gradient_boosting'])
def test_regression_model_menu_is_bounded_and_scores_outside_unit_interval(model, monkeypatch):
    monkeypatch.setenv('LOKY_MAX_CPU_COUNT', '1')
    from study.problem import ProblemSpec
    from study.tasks import get_adapter
    value = profile('tabular_regression', 'rmse')
    value['search_space']['models'] = [model]
    value['evaluation']['additional_metrics'] = ['mae', 'r2']
    adapter = get_adapter(ProblemSpec.from_dict(value))
    pipeline = adapter.build_pipeline(adapter.reference_config, seed=3)
    X = np.arange(160).reshape(80, 2)
    y = X[:, 0]*7 + np.sin(X[:, 1])*100
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        pipeline.fit(X[:60], y[:60])
        metrics = adapter.metrics(pipeline, X[60:], y[60:])
    assert metrics['rmse'] > 1
    assert metrics['mae'] > 1
    assert metrics['r2'] <= 1


@pytest.mark.parametrize('labels', [np.tile([.5, 1.5], 60), np.tile(np.asarray(['cat', 'dog'], dtype='S3'), 60)])
def test_classification_rejects_continuous_targets_before_preparing(tmp_path, labels):
    from study.problem import ProblemSpec
    from study.science import prepare_dataset
    value = profile()
    source = tmp_path / 'continuous.npz'
    np.savez(source, X=np.ones((120, 2)), y=labels)
    value['dataset'] = {'format': 'npz', 'path': str(source), 'feature_array': 'X', 'target_array': 'y'}
    with pytest.raises(ValueError, match='categorical'):
        prepare_dataset(tmp_path / 'data', problem=ProblemSpec.from_dict(value))
    assert not (tmp_path / 'data/train.npz').exists()


def test_multiclass_auc_is_macro_probability_auc_with_permuted_imbalanced_labels():
    from sklearn.metrics import roc_auc_score
    from study.problem import ProblemSpec
    from study.tasks import get_adapter
    labels = np.asarray(['zebra']*9 + ['ant']*3 + ['mole']*2)
    order = np.asarray(['mole', 'zebra', 'ant'])
    probabilities = np.random.default_rng(19).dirichlet([1, 2, 3], size=len(labels))
    class ProbabilityPipeline:
        classes_ = order
        def predict_proba(self, X):
            return probabilities
        def predict(self, X):
            raise AssertionError('AUC must use probabilities, never hard predictions')
    adapter = get_adapter(ProblemSpec.from_dict(profile(metric='roc_auc_ovr_macro')))
    actual = adapter.metrics(ProbabilityPipeline(), np.zeros((len(labels), 1)), labels)['roc_auc_ovr_macro']
    individual = [roc_auc_score(labels == label, probabilities[:, index]) for index, label in enumerate(order)]
    expected = float(np.mean(individual))
    weighted = float(np.average(individual, weights=[np.sum(labels == label) for label in order]))
    hard_predictions = order[probabilities.argmax(axis=1)]
    hard_auc = float(np.mean([roc_auc_score(labels == label, hard_predictions == label) for label in order]))
    assert actual == pytest.approx(expected)
    assert actual != pytest.approx(weighted)
    assert actual != pytest.approx(hard_auc)


def test_multiclass_auc_rejects_binary_source_during_data_validation(tmp_path):
    from study.problem import ProblemSpec
    from study.science import load_problem_data, prepare_dataset
    value = profile(metric='roc_auc_ovr_macro')
    value['dataset']['n_classes'] = 2
    spec = ProblemSpec.from_dict(value)
    with pytest.raises(ValueError, match='at least three classes'):
        load_problem_data(spec)
    with pytest.raises(ValueError, match='at least three classes'):
        prepare_dataset(tmp_path / 'data', problem=spec)
    assert not (tmp_path / 'data').exists()


def test_multiclass_auc_official_test_must_include_all_training_classes(tmp_path):
    from study.problem import ProblemSpec
    from study.science import prepare_dataset
    source = tmp_path / 'four-classes.npz'
    np.savez(source, X=np.ones((160, 4)), y=np.tile(np.arange(4), 40), test_X=np.ones((30, 4)), test_y=np.tile(np.arange(3), 10))
    value = profile(metric='roc_auc_ovr_macro')
    value['dataset'] = {'format': 'npz', 'path': str(source), 'feature_array': 'X', 'target_array': 'y', 'test_feature_array': 'test_X', 'test_target_array': 'test_y'}
    value['evaluation']['split'] = {'train': .8, 'validation': .2, 'test': 'official'}
    with pytest.raises(ValueError, match='all classes'):
        prepare_dataset(tmp_path / 'data', problem=ProblemSpec.from_dict(value))
    assert not (tmp_path / 'data').exists()


def test_multiclass_auc_worker_and_heldout_evaluator_use_same_probability_metric(tmp_path):
    from sklearn.metrics import roc_auc_score
    from study.problem import ProblemSpec
    from study.science import prepare_dataset, run_trial, evaluate_selected
    from study.tasks import get_adapter
    source = tmp_path / 'mnist-shaped-fixture.npz'
    rng = np.random.default_rng(4)
    y = np.asarray(['zebra']*60 + ['ant']*40 + ['mole']*20)
    test_y = np.asarray(['zebra']*20 + ['ant']*15 + ['mole']*10)
    X = rng.normal(size=(len(y), 2, 2))
    test_X = rng.normal(size=(len(test_y), 2, 2))
    np.savez(source, pixels=X, labels=y, official_pixels=test_X, official_labels=test_y)
    value = profile(metric='roc_auc_ovr_macro')
    value['dataset'] = {'format': 'npz', 'path': str(source), 'feature_array': 'pixels', 'target_array': 'labels', 'test_feature_array': 'official_pixels', 'test_target_array': 'official_labels', 'flatten': True}
    value['evaluation']['split'] = {'train': .8, 'validation': .2, 'test': 'official'}
    value['evaluation']['additional_metrics'] = ['accuracy', 'macro_f1']
    spec = ProblemSpec.from_dict(value)
    data = tmp_path / 'data'
    prepare_dataset(data, problem=spec)
    adapter = get_adapter(spec)
    assert adapter.describe(data)['adapter']['version'] == adapter.version
    result = asyncio.run(run_trial(data, tmp_path / 'trial', adapter.reference_config, seed=7, timeout=20))
    assert result['status'] == 'completed', result
    assert result['score'] == result['metrics']['roc_auc_ovr_macro']
    assert 'validation_auc' not in result
    pipeline = joblib.load(result['artifact'])['pipeline']
    def expected_score(path):
        with np.load(path) as partition:
            probabilities = pipeline.predict_proba(partition['X'])
            return float(np.mean([roc_auc_score(partition['y'] == label, probabilities[:, index]) for index, label in enumerate(pipeline.classes_)]))
    assert result['score'] == pytest.approx(expected_score(data / 'validation.npz'))
    test = evaluate_selected(data, tmp_path / 'run', {'best': result, 'useful': result})
    assert test['best'] == test['useful']
    assert test['best']['status'] == 'completed'
    assert test['best']['score'] == test['best']['metrics']['roc_auc_ovr_macro']
    assert test['best']['score'] == pytest.approx(expected_score(data / 'test.npz'))
    assert 'test_auc' not in test['best']
