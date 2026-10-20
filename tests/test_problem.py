"""Declarative profiles reject unsafe or scientifically inconsistent requests."""
import copy
import json

import pytest


def profile(task='tabular_classification', metric='accuracy'):
    return {'schema_version': 1, 'id': 'custom', 'task': task, 'brief': 'Predict the declared outcome.',
            'dataset': {'format': 'synthetic', 'n_samples': 120, 'n_features': 6, **({'n_classes': 3} if task.endswith('classification') else {})},
            'evaluation': {'split': {'train': .6, 'validation': .2, 'test': .2, 'seed': 42},
                           'objective': {'metric': metric, 'direction': 'minimize' if metric in ('rmse', 'mae') else 'maximize'},
                           'additional_metrics': []},
            'targets': [{'name': 'useful', 'value': .8 if metric in ('accuracy', 'roc_auc', 'roc_auc_ovr_macro', 'macro_f1') else 30}],
            'search_space': {'preset': task, 'models': ['logistic'] if task.endswith('classification') else ['ridge']}}


def test_profile_roundtrip_relative_path_and_immutable_identity(tmp_path):
    from study.problem import ProblemSpec, load_problem
    value = profile()
    value['dataset'] = {'format': 'csv', 'path': 'table.csv', 'header': True, 'target_column': 'species'}
    path = tmp_path / 'problem.json'
    path.write_text(json.dumps(value))
    spec = load_problem(path)
    assert spec.dataset['path'] == str(tmp_path / 'table.csv')
    assert ProblemSpec.from_dict(spec.to_dict()).fingerprint == spec.fingerprint
    value['brief'] = 'changed'
    assert spec.brief != value['brief']
    clone = spec.to_dict()
    clone['brief'] = 'changed'
    assert spec.brief != clone['brief']


@pytest.mark.parametrize('mutate', [
    lambda p: p.update(code='evil'),
    lambda p: p['evaluation']['objective'].update(direction='minimize'),
    lambda p: p['evaluation']['split'].update(train=.9),
    lambda p: p['targets'].append({'name': 'useful', 'value': .9}),
    lambda p: p['targets'][0].update(value=float('nan')),
    lambda p: p['targets'][0].update(value=2),
    lambda p: p['search_space'].update(models=['shell']),
    lambda p: p['dataset'].update(download='https://untrusted'),
])
def test_profile_rejects_unknown_invalid_and_nonfinite(mutate):
    from study.problem import ProblemSpec
    value = profile()
    mutate(value)
    with pytest.raises(ValueError):
        ProblemSpec.from_dict(value)


def test_bounded_override_can_only_narrow():
    from study.problem import ProblemSpec
    from study.tasks import get_adapter
    value = profile()
    value['search_space']['parameters'] = {'logistic': {'C': {'minimum': .1, 'maximum': 2}}}
    adapter = get_adapter(ProblemSpec.from_dict(value))
    adapter.validate_config({'model': 'logistic', 'preprocessing': 'none', 'params': {'C': 1}})
    with pytest.raises(ValueError):
        adapter.validate_config({'model': 'logistic', 'preprocessing': 'none', 'params': {'C': 20}})
    value['search_space']['parameters']['logistic']['C']['maximum'] = 1000
    with pytest.raises(ValueError):
        ProblemSpec.from_dict(value)


def test_auc_requires_declared_positive_class():
    from study.problem import ProblemSpec
    value = profile(metric='roc_auc')
    with pytest.raises(ValueError, match='positive'):
        ProblemSpec.from_dict(value)
    value['dataset']['positive_class'] = 1
    assert ProblemSpec.from_dict(value).objective['metric'] == 'roc_auc'


def test_yaml_duplicate_fields_and_executable_tags_rejected(tmp_path):
    from study.problem import load_problem
    path = tmp_path / 'bad.yaml'
    for text in ('id: a\nid: b\n', '!!python/object/apply:os.system [echo unsafe]'):
        path.write_text(text)
        with pytest.raises(ValueError):
            load_problem(path)


@pytest.mark.parametrize('override', [
    {'minimum': .01, 'maximum': .02, 'enum': [.5]},
    {'anyOf': [{'type': 'number'}]},
    {'type': 'string'},
    {'minimum': float('nan')},
])
def test_inconsistent_or_executable_schema_overrides_rejected(override):
    from study.problem import ProblemSpec
    value = profile()
    value['search_space']['parameters'] = {'logistic': {'C': override}}
    with pytest.raises(ValueError):
        ProblemSpec.from_dict(value)


def test_reserved_best_target_and_non_string_metric_rejected():
    from study.problem import ProblemSpec
    value = profile()
    value['targets'][0]['name'] = 'best'
    with pytest.raises(ValueError):
        ProblemSpec.from_dict(value)
    value = profile()
    value['evaluation']['objective']['metric'] = ['accuracy']
    with pytest.raises(ValueError):
        ProblemSpec.from_dict(value)


def test_all_bundled_profiles_validate_without_loading_datasets():
    from pathlib import Path
    from study.problem import load_problem
    from study.tasks import get_adapter
    for path in (Path(__file__).parents[1] / 'study/problems').glob('*.yaml'):
        spec = load_problem(path)
        adapter = get_adapter(spec)
        adapter.validate_config(adapter.reference_config)


def test_multiclass_auc_registry_direction_bounds_and_no_positive_class():
    from study.problem import METRICS, ProblemSpec, validate_metric_value
    value = profile(metric='roc_auc_ovr_macro')
    spec = ProblemSpec.from_dict(value)
    assert spec.objective == {'metric': 'roc_auc_ovr_macro', 'direction': 'maximize'}
    assert METRICS['roc_auc_ovr_macro']['task'] == 'tabular_classification'
    for invalid in (-.1, 1.1, float('nan'), True):
        with pytest.raises(ValueError):
            validate_metric_value('roc_auc_ovr_macro', invalid)
    value['dataset']['positive_class'] = 1
    with pytest.raises(ValueError, match='positive_class'):
        ProblemSpec.from_dict(value)


@pytest.mark.parametrize('objective,additional,positive', [
    ('accuracy', ['roc_auc_ovr_macro'], 1),
    ('roc_auc_ovr_macro', ['roc_auc'], 1),
    ('roc_auc', ['roc_auc_ovr_macro'], 1),
    ('roc_auc_ovr_macro', ['rmse'], None),
])
def test_multiclass_auc_incompatible_additional_metrics_rejected(objective, additional, positive):
    from study.problem import ProblemSpec
    value = profile(metric=objective)
    value['evaluation']['additional_metrics'] = additional
    if positive is not None:
        value['dataset']['positive_class'] = positive
    with pytest.raises(ValueError):
        ProblemSpec.from_dict(value)
