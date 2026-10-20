"""Scientific diagnostics explain equivalence without changing execution."""
import asyncio
import copy
import json

from study.problem import ProblemSpec
from tests.test_problem import profile


def forest(max_features='sqrt', *, preprocessing='none'):
    return {'model': 'random_forest', 'preprocessing': preprocessing, 'params': {'max_features': max_features}}


def describe(config, *, seed=7, project=None, problem=None):
    from study.diagnostics import describe_experiment
    return describe_experiment(config, problem=problem, project={'n_features': 10} if project is None else project, seed=seed)


def test_rf_aliases_resolve_to_three_features_and_warn_only_completed_history():
    from study.diagnostics import experiment_diagnostic
    previous = describe(forest())
    candidate = describe(forest('log2'))
    assert previous['effective_config']['params']['max_features'] == 3
    assert previous['fingerprint'] == candidate['fingerprint']
    history = [{'trial_id': 2, 'status': 'completed', 'config': forest(), 'seed': 7, **previous}, {'trial_id': 3, 'status': 'failed', **previous}]
    result = experiment_diagnostic(forest('log2'), problem=None, project={'feature_names': list('abcdefghij')}, seed=7, history=history)
    assert result['equivalent_trial_ids'] == [2]
    assert result['warning'].endswith('.')
    assert '2' in result['warning']


def test_omitted_defaults_equal_explicit_defaults_without_mutating_input():
    omitted = {'model': 'logistic', 'preprocessing': 'standard', 'params': {}}
    original = copy.deepcopy(omitted)
    explicit = copy.deepcopy(omitted)
    explicit['params'] = {'C': 1.0, 'max_iter': 300}
    assert describe(omitted)['fingerprint'] == describe(explicit)['fingerprint']
    assert describe(omitted)['effective_config']['params']['solver'] == 'lbfgs'
    assert omitted == original


def test_seed_preprocessing_data_and_unknown_feature_counts_are_not_aliases():
    base = describe(forest())['fingerprint']
    assert base != describe(forest(), seed=8)['fingerprint']
    assert base != describe(forest(preprocessing='standard'))['fingerprint']
    assert describe(forest(), project={})['fingerprint'] != describe(forest('log2'), project={})['fingerprint']
    assert describe(forest(), project={'n_features': 16})['fingerprint'] == describe(forest('log2'), project={'n_features': 16})['fingerprint']
    assert describe(forest(), project={'n_features': 25})['fingerprint'] != describe(forest('log2'), project={'n_features': 25})['fingerprint']
    assert describe(forest(), project={'data_fingerprint': 'a'})['fingerprint'] != describe(forest(), project={'data_fingerprint': 'b'})['fingerprint']


def test_generic_and_legacy_constructor_defaults_and_metric_provenance():
    definition = profile('tabular_regression', 'rmse')
    definition['search_space']['models'] = ['histogram_gradient_boosting']
    problem = ProblemSpec.from_dict(definition)
    config = {'model': 'histogram_gradient_boosting', 'preprocessing': 'none', 'params': {}}
    legacy = describe(config)
    generic = describe(config, problem=problem)
    assert legacy['effective_config']['params']['max_iter'] == 100
    assert legacy['effective_config']['params']['l2_regularization'] == 0.0
    assert generic['effective_config']['params']['max_iter'] == 200
    assert generic['effective_config']['params']['l2_regularization'] == 1.0
    assert generic['provenance']['metric'] == 'rmse'
    assert generic['provenance']['direction'] == 'minimize'
    assert generic['provenance']['split'] == 'validation'
    assert generic['provenance']['seed'] == 7
    assert generic['provenance']['n_features'] == 10
    assert generic['provenance']['sklearn_version']
    assert legacy['fingerprint'] != generic['fingerprint']


def test_diagnostics_do_not_copy_secrets_or_fit_models(monkeypatch):
    from sklearn.ensemble import RandomForestClassifier
    def forbidden(*args, **kwargs):
        raise AssertionError('diagnostics must not train')
    monkeypatch.setattr(RandomForestClassifier, 'fit', forbidden)
    result = describe(forest(), project={'n_features': 10, 'api_key': 'NEVER-COPY', 'test_labels': [1, 0]})
    encoded = json.dumps(result, allow_nan=False)
    assert 'NEVER-COPY' not in encoded
    assert 'test_labels' not in encoded


def test_history_without_seed_or_with_changed_implementation_does_not_match():
    from study.diagnostics import experiment_diagnostic
    prior = describe(forest())
    prior['provenance']['sklearn_version'] = 'different'
    history = [{'trial_id': 1, 'status': 'completed', 'config': forest()}, {'trial_id': 2, 'status': 'completed', 'seed': 7, 'config': forest(), **prior}]
    result = experiment_diagnostic(forest(), problem=None, project={'n_features': 10}, seed=7, history=history)
    assert result['equivalent_trial_ids'] == []
    assert result['warning'] is None


def test_run_trial_reports_actual_parameters_without_heldout_data(tmp_path):
    from study.science import prepare_dataset, run_trial
    data = tmp_path / 'data'
    prepare_dataset(data, synthetic=True, seed=3)
    (data / 'test.npz').unlink()
    config = forest('log2')
    config['params']['n_estimators'] = 10
    result = asyncio.run(run_trial(data, tmp_path / 'trial', config, seed=7, timeout=20, cores=2))
    assert result['status'] == 'completed', result
    assert result['effective_config']['params']['max_features'] == 3
    assert result['actual_effective_config']['params']['max_features'] == 3
    assert result['actual_effective_config']['params']['n_jobs'] == 2
    assert result['provenance']['split'] == 'validation'
    assert result['fingerprint']
    assert 'test_labels' not in json.dumps(result)


def test_unknown_feature_count_preserves_integer_and_fraction_semantics():
    # Historical estimators retain their semantics even though new tool requests
    # must use the unambiguous string "all".
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import Pipeline
    from study.diagnostics import pipeline_effective_config
    integer = Pipeline([('scale', 'passthrough'), ('model', RandomForestClassifier(max_features=1))])
    fraction = Pipeline([('scale', 'passthrough'), ('model', RandomForestClassifier(max_features=1.0))])
    assert type(pipeline_effective_config(integer, forest(1))['params']['max_features']) is int
    assert type(pipeline_effective_config(fraction, forest(1.0))['params']['max_features']) is float
    assert describe(forest('all'))['effective_config']['params']['max_features'] == 10
    numeric = {'model': 'logistic', 'preprocessing': 'none', 'params': {'C': 1}}
    decimal = {'model': 'logistic', 'preprocessing': 'none', 'params': {'C': 1.0}}
    assert describe(numeric)['fingerprint'] == describe(decimal)['fingerprint']


def test_worker_reports_fitted_iterations_in_agent_context(tmp_path):
    import joblib
    from study.science import prepare_dataset, run_trial
    from study.controller import agent_result
    data = tmp_path / 'data'
    prepare_dataset(data, synthetic=True, seed=3)
    (data / 'test.npz').unlink()
    config = {'model': 'histogram_gradient_boosting', 'preprocessing': 'standard',
              'params': {'max_iter': 100}}
    result = asyncio.run(run_trial(data, tmp_path / 'trial', config, seed=7, timeout=20))
    assert result['status'] == 'completed', result
    estimator = joblib.load(result['artifact'])['pipeline'].steps[-1][1]
    fit = agent_result(result)['fit_diagnostics']
    assert fit == {'iterations_completed': int(estimator.n_iter_), 'iteration_limit': 100,
                   'early_stopping_enabled': bool(estimator.do_early_stopping_),
                   'stopped_before_limit': bool(estimator.n_iter_ < 100)}
