import asyncio
import json

from study.config import StudyConfig
from study.controller import run_one, tools_for
from study.fake import FakeModel


def test_context_only_tools_removed():
    assert [x['function']['name'] for x in tools_for('researcher', StudyConfig())] == ['run_analysis']
    assert tools_for('supervisor', StudyConfig(condition='frequent')) == []
    assert {x['function']['name'] for x in tools_for('supervisor', StudyConfig(condition='periodic_reflection_literature'))} == {'literature_search', 'literature_fetch'}


def test_equivalent_trial_reuses_evidence_without_training_or_trial_slot(tmp_path):
    fits = []
    async def fit(data, output, config, **kwargs):
        fits.append(config)
        return {'status': 'completed', 'validation_auc': .9, 'metrics': {'roc_auc': .9}, 'artifact': 'fixture', 'artifact_hash': 'fixture'}
    options = [
        {'model': 'random_forest', 'preprocessing': 'none', 'params': {'max_features': 'sqrt'}},
        {'model': 'random_forest', 'preprocessing': 'none', 'params': {'max_features': 'log2'}},
        {'model': 'logistic', 'preprocessing': 'standard', 'params': {'C': 2}},
    ]
    model = FakeModel(options)
    summary = asyncio.run(run_one(StudyConfig(trial_cap=2), tmp_path, tmp_path/'run', model,
        trial_runner=fit, project={'feature_names': ['x']*10}))
    assert len(fits) == 2
    assert fits[-1]['model'] == 'logistic'
    assert summary['trials'] == 2 and summary['stop_reason'] == 'trial_cap'
    assert summary['accounting']['calls'] == 3
    events = [json.loads(line) for line in (tmp_path/'run/events.jsonl').read_text().splitlines()]
    reused = [e for e in events if e['type'] == 'experiment_reused']
    assert len(reused) == 1 and reused[0]['matched_trial_ids'] == [1]
    assert sum(e['type'] == 'trial_started' for e in events) == 2


def test_repeated_duplicate_proposals_terminate_with_nonzero_search_status(tmp_path):
    from study.__main__ import require_successful_runs
    fits = []
    async def fit(data, output, config, **kwargs):
        fits.append(config)
        return {'status': 'completed', 'validation_auc': .9, 'artifact': 'fixture', 'artifact_hash': 'fixture'}
    model = FakeModel([{'model': 'logistic', 'preprocessing': 'standard', 'params': {}}])
    summary = asyncio.run(run_one(StudyConfig(trial_cap=2, max_turns_without_trial=3), tmp_path, tmp_path/'run', model,
        trial_runner=fit, project={}))
    assert len(fits) == 1 and summary['trials'] == 1
    assert summary['stop_reason'] == 'no_progress'
    import pytest
    with pytest.raises(RuntimeError, match="no_progress"):
        require_successful_runs([summary])


def test_profile_offline_options_are_distinct_and_respect_bounds():
    from study.fake import bounded_options
    from study.problem import ProblemSpec
    from study.tasks import get_adapter
    from test_problem import profile
    value = profile()
    value['search_space']['parameters'] = {'logistic': {'C': {'minimum': .1, 'maximum': .5}}}
    adapter = get_adapter(ProblemSpec.from_dict(value))
    options = bounded_options(adapter)
    assert len(options) >= 2
    assert len({json.dumps(c, sort_keys=True) for c in options}) == len(options)
    for config in options:
        adapter.validate_config(config)


def test_recovery_preserves_old_policy_without_restarting_old_runtime(tmp_path):
    from study.controller import recover_run
    from study.problem import legacy_problem
    config = StudyConfig().to_dict() | {'reasoning_policy': 'grounded_v1'}
    problem = legacy_problem()
    (tmp_path/'resolved-config.json').write_text(json.dumps({'config': config,
        'problem': problem.to_dict(), 'problem_hash': problem.fingerprint}))
    (tmp_path/'events.jsonl').write_text('')
    summary = recover_run(tmp_path)
    assert summary['config']['reasoning_policy'] == 'grounded_v1'
    assert summary['stop_reason'] == 'interrupted'
