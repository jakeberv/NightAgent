"""The recorded change must come from executable settings, not model prose."""
from study.problem import legacy_problem
from study.diagnostics import describe_experiment
import pytest
from pathlib import Path


def test_change_uses_resolved_defaults_and_actual_parameter_delta():
    from study.diagnostics import configuration_change
    problem = legacy_problem()
    baseline = {'trial_id': 7, 'config': {'model': 'logistic',
        'preprocessing': 'standard', 'params': {'C': 1}}, 'seed': 42}
    candidate = describe_experiment({'model': 'logistic', 'preprocessing': 'standard',
        'params': {'C': 2, 'max_iter': 300}}, problem=problem, project={}, seed=42)
    # The adapter default is 300: spelling it explicitly is not a second change.
    change = configuration_change(candidate, baseline, problem=problem, project={}, seed=42)
    assert 'params.C: 1.0 -> 2.0' in change
    assert 'max_iter' not in change


def test_unchanged_effective_configuration_cannot_claim_a_parameter_change():
    from study.diagnostics import configuration_change
    problem = legacy_problem()
    baseline = {'trial_id': 7, 'config': {'model': 'random_forest',
        'preprocessing': 'standard', 'params': {'n_estimators': 100,
        'max_depth': 20, 'max_features': 'sqrt'}}, 'seed': 42}
    candidate = describe_experiment(baseline['config'], problem=problem,
        project={'n_features': 784}, seed=42)
    change = configuration_change(candidate, baseline, problem=problem,
        project={'n_features': 784}, seed=42)
    assert change == 'No effective configuration change from trial 7.'


def test_independent_experiment_does_not_invent_a_baseline():
    from study.diagnostics import configuration_change
    assert configuration_change({}, None, problem=legacy_problem(), project={}, seed=42) == (
        'Independent experiment; no baseline was selected.')


def test_old_saved_config_is_readable_but_cannot_launch_a_new_run(tmp_path):
    import asyncio
    import pytest
    from study.config import StudyConfig
    from study.controller import run_one
    saved = StudyConfig(decision_protocol='structured_v1', device='cpu')
    assert saved.to_dict()['decision_protocol'] == 'structured_v1'
    with pytest.raises(ValueError, match='structured_v2'):
        asyncio.run(run_one(saved, tmp_path, tmp_path / 'old', object(), project={}))
    assert not (tmp_path / 'old').exists()


@pytest.mark.parametrize('filename', ['pilot-config.json', 'magic-pilot-config.json',
                                    'fashion-pilot-config.json', 'supervisor-comparison-config.json'])
def test_documented_pilot_configuration_passes_current_execution_gate(filename):
    from study.__main__ import load_config
    from study.controller import execution_config
    config = load_config(Path(__file__).resolve().parents[1] / 'study' / filename)
    resolved = execution_config(config, None)
    assert resolved.device == 'cpu'
