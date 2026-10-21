"""Regression coverage for the live smoke failures and five declared treatments."""
import asyncio
from datetime import datetime, timedelta, timezone
import json

import pytest

from study.config import StudyConfig
from study.controller import run_one
from study.fake import FakeModel
from study.reasoning import resolve_contract_evidence
from study.suite import run_suite
from test_reasoning_controller import trial
from test_report_analysis import paired_run


class AdviceReader(FakeModel):
    """Reproduce the live model's interpretation of null last_supervisor_feedback."""
    def __init__(self):
        super().__init__(options=[{'model': 'logistic', 'preprocessing': 'standard',
                                  'params': {'C': n}} for n in range(1, 8)])
        self.research_contexts = []

    async def complete(self, messages, tools, *, timeout):
        response = await super().complete(messages, tools, timeout=timeout)
        if messages[0]['content'].startswith('ROLE: researcher'):
            ctx = json.loads(messages[1]['content'])
            self.research_contexts.append(ctx)
            function = response['message']['tool_calls'][0]['function']
            args = json.loads(function['arguments'])
            args['intent']['supervisor_response'] = 'modified' if ctx['last_supervisor_feedback'] else 'not_applicable'
            function['arguments'] = json.dumps(args)
        return response


@pytest.mark.parametrize('condition', ['periodic', 'periodic_reflection', 'researcher_alone'])
def test_framing_remains_active_until_review_without_contract_repairs(tmp_path, condition):
    model = AdviceReader()
    result = asyncio.run(run_one(StudyConfig(condition=condition, trial_cap=7), tmp_path,
        tmp_path/'run', model, trial_runner=trial, project={}))
    events = [json.loads(s) for s in (tmp_path/'run/events.jsonl').read_text().splitlines()]
    assert result['stop_reason'] == 'trial_cap' and result['trials'] == 7
    assert len(model.research_contexts) == 7
    assert all(e['valid'] for e in events if e['type'].endswith('_contract'))
    if condition == 'researcher_alone':
        assert all(c['last_supervisor_feedback'] is None for c in model.research_contexts)
    else:
        framing = next(e['contract'] for e in events if e['type'] == 'framing')
        reviews = [e for e in events if e['type'] == 'review']
        assert [e['after_trial'] for e in reviews] == [3, 6]
        for c in model.research_contexts[:3]:
            assert c['last_supervisor_feedback']['recommendation'] == framing['recommendation']
        assert model.research_contexts[3]['last_supervisor_feedback']['evidence'] == reviews[0]['contract']['evidence']
        assert model.research_contexts[6]['last_supervisor_feedback']['evidence'] == reviews[1]['contract']['evidence']


def test_nonmetric_evidence_names_available_metrics_in_repair_message():
    history = [{'trial_id': 1, 'status': 'completed', 'metrics': {'accuracy': .8, 'macro_f1': .79}}]
    with pytest.raises(ValueError) as error:
        resolve_contract_evidence({'evidence': [{'trial_id': 1, 'metric': 'fit_diagnostics'}]}, history)
    message = str(error.value)
    assert 'fit_diagnostics' in message and 'accuracy' in message and 'macro_f1' in message
    good = resolve_contract_evidence({'evidence': [{'trial_id': 1, 'metric': 'accuracy'}]}, history)
    assert good['evidence'][0]['value'] == .8


@pytest.mark.parametrize('base_memory', [True, False])
def test_targeted_suite_preserves_five_distinct_treatments_and_matched_seeds(tmp_path, base_memory):
    configs = []
    async def runner(config, data_dir, run_dir, model):
        configs.append(config)
        run_dir.mkdir(parents=True)
        return {'stop_reason': 'trial_cap'}
    asyncio.run(run_suite(StudyConfig(comparison='apprentice_interactions', allowance_seconds=1,
        condition='periodic_reflection', lesson_memory=base_memory),
        tmp_path, tmp_path/'suite', repeats=2,
        deadline=datetime.now(timezone.utc)+timedelta(seconds=60), reserve_seconds=5,
        model_factory=lambda config: None, runner=runner))
    schedule = json.loads((tmp_path/'suite/suite.json').read_text())['schedule']
    assert len({x['run_id'] for x in schedule}) == 10
    assert {x['arm'] for x in schedule} == {'researcher_alone', 'frequent', 'periodic',
                                          'periodic_reflection', 'periodic_reflection_no_memory'}
    assert {(x['arm'], x['lesson_memory']) for x in schedule} == {
        ('researcher_alone', True), ('frequent', True), ('periodic', True),
        ('periodic_reflection', True), ('periodic_reflection_no_memory', False)}
    for repeat in (0, 1):
        subset = [c for c in configs if c.repeat == repeat]
        assert len(subset) == 5
        assert {c.training_seed for c in subset} == {42+repeat}
        assert {(c.condition,c.lesson_memory) for c in subset} == {
            ('researcher_alone',True),('frequent',True),('periodic',True),
            ('periodic_reflection',True),('periodic_reflection',False)}
        assert all(c.supervisor_strategy=='night_science' and not c.literature for c in subset)


def write_targeted(root, **memory_changes):
    common = dict(comparison='apprentice_interactions', supervisor_strategy='night_science',
                  context_policy='active_advice_v1')
    for name, condition, memory in [('a','researcher_alone',True),('b','frequent',True),
            ('c','periodic',True),('d','periodic_reflection',True),('e','periodic_reflection',False)]:
        changes = {**common, 'lesson_memory': memory}
        if name == 'd': changes.update(memory_changes)
        paired_run(root,name,condition,**changes)


def test_report_pairs_only_declared_adjacent_axes_including_memory(tmp_path):
    from study.report import build_report_data
    write_targeted(tmp_path)
    data = build_report_data(tmp_path)
    assert len(data['conditions']) == 5
    assert [(p['condition_a'],p['condition_b']) for p in data['paired_comparisons'] if p['matched_pairs']] == [
        ('researcher_alone','frequent'),('frequent','periodic'),
        ('periodic','periodic_reflection'),('periodic_reflection_no_memory','periodic_reflection')]
    assert all(p['matched_pairs']==1 for p in data['paired_comparisons'])


@pytest.mark.parametrize('changes',[{'model':'other'}, {'context_policy':'old'},
                                  {'training_seed':77}, {'supervisor_strategy':'standard'},
                                  {'lesson_memory':1}, {'lesson_memory':None}])
def test_targeted_memory_pair_does_not_hide_other_mismatches(tmp_path, changes):
    from study.report import build_report_data
    write_targeted(tmp_path,**changes)
    pairs=build_report_data(tmp_path)['paired_comparisons']
    assert not any(p['matched_pairs'] and {p['condition_a'],p['condition_b']} ==
                   {'periodic_reflection_no_memory', 'periodic_reflection'} for p in pairs)


def test_targeted_memory_contrast_reports_memory_on_minus_off(tmp_path):
    from study.report import build_report_data
    common = dict(comparison='apprentice_interactions', supervisor_strategy='night_science')
    paired_run(tmp_path, 'off', 'periodic_reflection', score=.7, lesson_memory=False, **common)
    paired_run(tmp_path, 'on', 'periodic_reflection', score=.9, lesson_memory=True, **common)
    pair, = build_report_data(tmp_path)['paired_comparisons']
    assert (pair['condition_a'], pair['condition_b']) == (
        'periodic_reflection_no_memory', 'periodic_reflection')
    assert pair['matched_pairs'] == 1
    assert pair['metrics']['best_score']['mean_delta'] == pytest.approx(.2)


def test_legacy_schedules_still_do_not_pair_memory_variants(tmp_path):
    from study.report import build_report_data
    paired_run(tmp_path,'off','periodic_reflection',comparison='schedules',lesson_memory=False)
    paired_run(tmp_path,'on','periodic_reflection',comparison='schedules',lesson_memory=True)
    assert not any(p['matched_pairs'] for p in build_report_data(tmp_path)['paired_comparisons'])


def test_targeted_aggregate_does_not_pool_different_models(tmp_path):
    from study.report import build_report_data
    common=dict(comparison='apprentice_interactions',supervisor_strategy='night_science',lesson_memory=True)
    paired_run(tmp_path,'one','periodic_reflection',model='model-one',score=.4,**common)
    paired_run(tmp_path,'two','periodic_reflection',model='model-two',score=.9,**common)
    data=build_report_data(tmp_path)
    assert len(data['conditions'])==2
    assert {row['analysis_group'] for row in data['runs']} == {
        'periodic_reflection [configuration 1]', 'periodic_reflection [configuration 2]'}


@pytest.mark.parametrize('memory', [True, False])
def test_cli_applies_condition_and_memory_as_one_valid_override(tmp_path, monkeypatch, memory):
    from types import SimpleNamespace
    from study import __main__ as cli
    config=tmp_path/'config.json'
    config.write_text(json.dumps({'comparison':'apprentice_interactions'}))
    class PreflightReached(Exception): pass
    def reached(*args): raise PreflightReached()
    monkeypatch.setattr(cli,'preflight_problem',reached)
    args=SimpleNamespace(command='run',config=config,problem=None,condition='periodic_reflection',
                         lesson_memory=memory,data=tmp_path,quiet=True,no_animation=True,verbose=False)
    with pytest.raises(PreflightReached):
        asyncio.run(cli.dispatch(args))


@pytest.mark.parametrize('command', ['run', 'suite'])
@pytest.mark.parametrize('configured,flag,expected', [
    (None, None, True), (False, None, False), (True, None, True),
    (True, '--no-lesson-memory', False), (False, '--lesson-memory', True),
])
def test_live_cli_memory_defaults_and_overrides_reach_provider_boundary(
        tmp_path, monkeypatch, command, configured, flag, expected):
    import sys
    from study import __main__ as cli
    from study.science import prepare_dataset
    data = tmp_path / 'data'
    prepare_dataset(data, synthetic=True)
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({} if configured is None else {'lesson_memory': configured}))
    class ConfigReached(Exception):
        def __init__(self, config): self.config = config
    def stop_before_provider(config): raise ConfigReached(config)
    monkeypatch.setattr(cli, 'live_model', stop_before_provider)
    argv = ['study', command, '--config', str(config), '--data', str(data),
            '--output', str(tmp_path / 'output'), '--quiet']
    if command == 'suite':
        argv += ['--deadline', (datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()]
    if flag:
        argv.append(flag)
    monkeypatch.setattr(sys, 'argv', argv)
    with pytest.raises(ConfigReached) as reached:
        cli.main()
    assert reached.value.config.lesson_memory is expected


@pytest.mark.parametrize('flag,expected', [
    (None, True), ('--lesson-memory', True), ('--no-lesson-memory', False),
])
def test_smoke_cli_memory_defaults_and_opt_out_reach_run_boundary(tmp_path, monkeypatch, flag, expected):
    import sys
    from study import __main__ as cli
    class ConfigReached(Exception):
        def __init__(self, config): self.config = config
    async def stop_before_run(config, *args, **kwargs): raise ConfigReached(config)
    monkeypatch.setattr(cli, 'run_one', stop_before_run)
    argv = ['study', 'smoke', '--output', str(tmp_path / 'output'), '--quiet']
    if flag:
        argv.append(flag)
    monkeypatch.setattr(sys, 'argv', argv)
    with pytest.raises(ConfigReached) as reached:
        cli.main()
    assert reached.value.config.lesson_memory is expected


def test_programmatic_smoke_inherits_memory_when_flag_is_absent(tmp_path, monkeypatch):
    from argparse import Namespace
    from study import __main__ as cli
    class ConfigReached(Exception):
        def __init__(self, config): self.config = config
    async def stop_before_run(config, *args, **kwargs): raise ConfigReached(config)
    monkeypatch.setattr(cli, 'run_one', stop_before_run)
    with pytest.raises(ConfigReached) as reached:
        asyncio.run(cli.dispatch(Namespace(command='smoke', output=tmp_path/'output', quiet=True)))
    assert reached.value.config.lesson_memory is True
