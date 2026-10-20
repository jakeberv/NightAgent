"""Matched supervision strategies must differ only in the intended treatment."""
import asyncio
from datetime import datetime, timedelta, timezone
import json

import pytest

from study.config import StudyConfig
from study.controller import run_one
from study.fake import FakeModel
from study.reasoning import validate_contract
from study.suite import run_suite
from test_reasoning_controller import trial


def standard_review():
    return {'summary': 'Compare the next bounded setting with the baseline.',
            'assessment': 'The baseline provides one validation observation.',
            'unresolved_question': 'Would changing model capacity improve the validation score?',
            'recommendation': 'Compare one permitted capacity setting with the baseline.',
            'expected_outcome': 'A higher score would favor that setting on this split.',
            'evidence': [{'trial_id': 1, 'metric': 'roc_auc', 'split': 'validation', 'value': .9}]}


def test_standard_contract_accepts_prior_review_shape_without_night_science_fields():
    history = [{'trial_id': 1, 'status': 'completed', 'metrics': {'roc_auc': .9}}]
    contract = standard_review()
    assert validate_contract(contract, 'supervisor', history, supervisor_strategy='standard') == []
    assert validate_contract(contract, 'supervisor', history, supervisor_strategy='night_science')
    contract['evidence'][0]['value'] = .99
    assert validate_contract(contract, 'supervisor', history, supervisor_strategy='standard')
    contract['evidence'] = []
    assert validate_contract(contract, 'supervisor', history, supervisor_strategy='standard')


class Observed(FakeModel):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def complete(self, messages, tools, *, timeout):
        self.calls.append((messages[0]['content'], json.loads(messages[1]['content']), tools))
        return await super().complete(messages, tools, timeout=timeout)


def test_strategies_share_initial_framing_and_permissions_but_change_later_reviews(tmp_path):
    observations = {}
    for strategy in ('standard', 'night_science'):
        config = StudyConfig(condition='frequent', supervisor_strategy=strategy, trial_cap=2)
        model = Observed()
        directory = tmp_path / strategy
        result = asyncio.run(run_one(config, tmp_path, directory, model, trial_runner=trial, project={}))
        assert result['stop_reason'] == 'trial_cap' and result['trials'] == 2
        assert result['accounting']['calls'] == 4
        assert [text.splitlines()[0] for text, _, _ in model.calls] == [
            'ROLE: supervisor', 'ROLE: researcher', 'ROLE: supervisor', 'ROLE: researcher']
        assert model.calls[0][2] == model.calls[2][2] == []
        events = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()]
        framing = next(e['contract'] for e in events if e['type'] == 'framing')
        assert framing['motivation'] and framing['hypothesis'] and framing['evidence'] == []
        assert model.calls[1][1]['initial_framing'] == framing
        review = next(e['contract'] for e in events if e['type'] == 'review')
        assert ('alternative_explanations' in review) == (strategy == 'night_science')
        assert ('cross_field_connection' in review) == (strategy == 'night_science')
        assert model.calls[3][1]['last_supervisor_feedback'] == review
        assert result['config']['supervisor_strategy'] == strategy
        observations[strategy] = model.calls
    assert observations['standard'][0][0] == observations['night_science'][0][0]
    assert observations['standard'][2][0] != observations['night_science'][2][0]


def test_three_arm_suite_freezes_unique_runs_and_matched_budgets(tmp_path):
    configs = []
    async def runner(config, data_dir, run_dir, model):
        configs.append(config)
        run_dir.mkdir(parents=True)
        return {'stop_reason': 'trial_cap'}
    directory = tmp_path / 'suite'
    config = StudyConfig(comparison='supervisor_strategies', allowance_seconds=1)
    asyncio.run(run_suite(config, tmp_path, directory, repeats=2,
        deadline=datetime.now(timezone.utc) + timedelta(seconds=60), reserve_seconds=5,
        model_factory=lambda config: None, runner=runner))
    assert len(configs) == 6
    for repeat in range(2):
        group = [c for c in configs if c.repeat == repeat]
        assert {(c.condition, c.supervisor_strategy) for c in group} == {
            ('researcher_alone', 'night_science'), ('frequent', 'standard'), ('frequent', 'night_science')}
        assert {c.training_seed for c in group} == {42 + repeat}
        assert not any(c.reflection or c.literature for c in group)
        settings = [{k: v for k, v in c.to_dict().items() if k not in ('condition', 'supervisor_strategy')}
                    for c in group]
        assert settings[0] == settings[1] == settings[2]
    manifest = json.loads((directory / 'suite.json').read_text())
    assert len({e['run_id'] for e in manifest['schedule']}) == 6
    assert {e['arm'] for e in manifest['schedule']} == {
        'researcher_alone', 'standard_supervisor', 'night_science_supervisor'}


def test_three_arm_deadline_counts_three_allowances_instead_of_five(tmp_path):
    async def runner(config, data_dir, run_dir, model):
        run_dir.mkdir(parents=True)
        return {'stop_reason': 'trial_cap'}
    result = asyncio.run(run_suite(StudyConfig(comparison='supervisor_strategies', allowance_seconds=10),
        tmp_path, tmp_path / 'suite', repeats=1,
        deadline=datetime.now(timezone.utc) + timedelta(seconds=45), reserve_seconds=5,
        model_factory=lambda config: None, runner=runner))
    assert len(result) == 3


@pytest.mark.parametrize('mismatch', [None, 'allowance_seconds', 'reasoning_policy', 'supervisor_policy'])
def test_reports_pair_all_three_arms_but_keep_other_config_differences_separate(tmp_path, mismatch):
    from test_report_analysis import paired_run
    from study.report import build_report_data
    for label, condition, strategy in (
        ('solo', 'researcher_alone', 'night_science'),
        ('standard', 'frequent', 'standard'), ('night', 'frequent', 'night_science')):
        config = dict(comparison='supervisor_strategies', supervisor_strategy=strategy,
                      supervisor_policy='supervision_v2', reasoning_policy='grounded_v2')
        if label == 'standard' and mismatch:
            config[mismatch] = 200 if mismatch == 'allowance_seconds' else 'other_version'
        paired_run(tmp_path, label, condition, **config)
    data = build_report_data(tmp_path)
    assert set(data['conditions']) == {'researcher_alone', 'standard_supervisor', 'night_science_supervisor'}
    comparisons = [c for c in data['paired_comparisons'] if c['matched_pairs']]
    assert len(comparisons) == (1 if mismatch else 3)
    if not mismatch:
        assert all(c['matched_pairs'] == 1 for c in comparisons)
    assert not any('Duplicate matched unit' in warning for warning in data['warnings'])


@pytest.mark.parametrize('strategy,condition', [(None, 'frequent'), ('unknown', 'frequent'),
                                              ('standard', 'periodic')])
def test_malformed_comparison_arm_is_excluded_from_pairing(tmp_path, strategy, condition):
    from test_report_analysis import paired_run
    from study.report import build_report_data
    common = dict(comparison='supervisor_strategies', supervisor_policy='supervision_v2')
    paired_run(tmp_path, 'solo', 'researcher_alone', supervisor_strategy='night_science', **common)
    paired_run(tmp_path, 'invalid', condition, supervisor_strategy=strategy, **common)
    report = build_report_data(tmp_path)
    assert not any(row['matched_pairs'] for row in report['paired_comparisons'])


def test_recovery_preserves_historical_supervisor_policy_without_relabeling(tmp_path):
    from study.controller import recover_run
    directory = tmp_path / 'run'
    asyncio.run(run_one(StudyConfig(condition='frequent', trial_cap=1), tmp_path,
        directory, FakeModel(), trial_runner=trial, project={}))
    frozen_path = directory / 'resolved-config.json'
    frozen = json.loads(frozen_path.read_text())
    frozen['config']['supervisor_policy'] = 'night_science_v1'
    del frozen['config']['supervisor_strategy']
    del frozen['config']['comparison']
    frozen_path.write_text(json.dumps(frozen))
    (directory / 'summary.json').unlink()
    events_path = directory / 'events.jsonl'
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    events_path.write_text(''.join(json.dumps(e) + '\n' for e in events if e['type'] != 'run_stopped'))
    summary = recover_run(directory)
    assert summary['config']['supervisor_policy'] == 'night_science_v1'
    assert 'supervisor_strategy' not in summary['config']
    assert summary['trials'] == 1 and summary['accounting']['calls'] == 2


def test_missing_three_arm_runs_retain_planned_strategy_in_report(tmp_path):
    from study.report import build_report_data
    config = StudyConfig(comparison='supervisor_strategies').to_dict()
    (tmp_path / 'suite.json').write_text(json.dumps({'config': config, 'schedule': [
        {'condition': 'researcher_alone', 'repeat': 0, 'run_id': 'solo', 'supervisor_strategy': 'night_science'},
        {'condition': 'frequent', 'repeat': 0, 'run_id': 'standard', 'supervisor_strategy': 'standard'},
        {'condition': 'frequent', 'repeat': 0, 'run_id': 'night', 'supervisor_strategy': 'night_science'}]}))
    report = build_report_data(tmp_path)
    assert set(report['conditions']) == {'researcher_alone', 'standard_supervisor', 'night_science_supervisor'}
    assert all(row['stop_reason'] == 'not_started' for row in report['runs'])


@pytest.mark.parametrize('field,value', [('supervisor_strategy', 'unknown'), ('comparison', 'unknown')])
def test_invalid_strategy_or_comparison_is_rejected(field, value):
    with pytest.raises(ValueError, match=field):
        StudyConfig(**{field: value})


@pytest.mark.parametrize('command', ['suite', 'smoke'])
def test_cli_three_arm_comparison_creates_distinct_reports_without_live_api(tmp_path, monkeypatch, command):
    import sys
    from study.__main__ import main
    from study.science import prepare_dataset
    from study.report import build_report_data
    output = tmp_path / command
    argv = ['study', command, '--output', str(output), '--comparison', 'supervisor_strategies', '--quiet']
    if command == 'suite':
        data = tmp_path / 'data'
        prepare_dataset(data, synthetic=True)
        config = tmp_path / 'config.json'
        config.write_text('{"trial_cap":2,"allowance_seconds":10}')
        class Offline(FakeModel):
            async def describe(self):
                return {'offline': True}
        monkeypatch.setattr('study.__main__.live_model', lambda config: Offline())
        argv += ['--config', str(config), '--data', str(data), '--repeats', '1',
                 '--reserve-seconds', '5', '--validation-only', '--deadline',
                 (datetime.now(timezone.utc) + timedelta(seconds=90)).isoformat()]
    monkeypatch.setattr(sys, 'argv', argv)
    main()
    report = build_report_data(output)
    assert len(report['runs']) == 3
    assert set(report['conditions']) == {'researcher_alone', 'standard_supervisor', 'night_science_supervisor'}
    assert all(row['stop_reason'] == 'trial_cap' for row in report['runs'])
    assert len(report['paired_comparisons']) == 3
    assert all(row['matched_pairs'] == 1 for row in report['paired_comparisons'])
    assert (output / 'report.html').exists()
    if command == 'suite':
        assert not (output / 'evaluation').exists()


def test_cli_can_select_standard_for_single_run(tmp_path, monkeypatch):
    import sys
    from study.__main__ import main
    from study.science import prepare_dataset
    data, output = tmp_path / 'data', tmp_path / 'run'
    prepare_dataset(data, synthetic=True)
    config = tmp_path / 'config.json'
    config.write_text('{"trial_cap":2,"allowance_seconds":10}')
    class Offline(FakeModel):
        async def describe(self):
            return {'offline': True}
    monkeypatch.setattr('study.__main__.live_model', lambda config: Offline())
    monkeypatch.setattr(sys, 'argv', ['study', 'run', '--config', str(config), '--data', str(data),
        '--output', str(output), '--supervisor-strategy', 'standard', '--condition', 'frequent', '--quiet'])
    main()
    result = json.loads((output / 'summary.json').read_text())
    assert result['config']['supervisor_strategy'] == 'standard'
    assert result['trials'] == 2 and result['stop_reason'] == 'trial_cap'
