"""Observable Night Science contracts and budgeted kickoff supervision."""
import asyncio
import copy
import json

import pytest

from study.config import CONDITIONS, StudyConfig
from study.controller import run_one
from study.recovery import recover_run
from study.fake import FakeModel
from study.reasoning import validate_contract
from test_reasoning_controller import trial


def review():
    return {
        'summary': 'Test whether stronger regularization improves validation performance.',
        'motivation': 'A controlled regularization test can guide the next use of limited compute.',
        'alternative_explanations': [
            'The current model may be overfitting.',
            'The apparent difference may reflect noise on this fixed split.'],
        'assessment': 'No completed trial yet distinguishes these explanations.',
        'unresolved_question': 'Does reducing C improve validation performance with other settings fixed?',
        'cross_field_connection': 'Statistical shrinkage suggests a regularization test; this analogy is unverified.',
        'recommendation': {'model': 'logistic', 'preprocessing': 'standard', 'params': {'C': .5}},
        'expected_outcome': 'A higher validation score with lower C would support further regularization tests.',
        'falsifying_outcome': 'An equal or lower score would weaken that prediction on this split.',
        'resource_check': 'Use one bounded fit at a time and reserve time for the next API call.',
        'evidence': [],
    }


@pytest.mark.parametrize('missing', [None, 'alternative_explanations', 'motivation',
                                   'cross_field_connection', 'falsifying_outcome', 'resource_check'])
def test_supervisor_requires_explicit_exploration_and_discriminating_review(missing):
    contract = review()
    if missing:
        del contract[missing]
    errors = validate_contract(contract, 'supervisor', [])
    assert bool(errors) == (missing is not None)


@pytest.mark.parametrize('alternatives', [[], ['A single explanation remains possible.'],
    ['The model may overfit.', 'The model may overfit.']])
def test_supervisor_requires_distinct_alternatives(alternatives):
    contract = review()
    contract['alternative_explanations'] = alternatives
    assert validate_contract(contract, 'supervisor', [])


def test_review_must_cite_completed_evidence_but_kickoff_and_failed_trials_need_none():
    contract = review()
    assert validate_contract(contract, 'supervisor', []) == []
    assert validate_contract(contract, 'supervisor', [{'trial_id': 1, 'status': 'failed'}]) == []
    history = [{'trial_id': 1, 'status': 'completed', 'metrics': {'roc_auc': .9}}]
    assert validate_contract(contract, 'supervisor', history)
    contract['evidence'] = [{'trial_id': 1, 'metric': 'roc_auc', 'split': 'validation', 'value': .9}]
    assert validate_contract(contract, 'supervisor', history) == []


class ObservedModel(FakeModel):
    def __init__(self):
        super().__init__()
        self.observed = []

    async def complete(self, messages, tools, *, timeout):
        role = messages[0]['content'].splitlines()[0].removeprefix('ROLE: ')
        context = json.loads(messages[1]['content'])
        self.observed.append((role, context, copy.deepcopy(tools)))
        return await super().complete(messages, tools, timeout=timeout)


@pytest.mark.parametrize('condition', CONDITIONS)
def test_kickoff_precedes_first_experiment_only_in_supervised_conditions(tmp_path, condition):
    model = ObservedModel()
    run_dir = tmp_path / 'run'
    summary = asyncio.run(run_one(StudyConfig(condition=condition, trial_cap=1),
        tmp_path, run_dir, model, trial_runner=trial, project={}))
    events = [json.loads(line) for line in (run_dir / 'events.jsonl').read_text().splitlines()]
    framed = [e for e in events if e['type'] == 'framing']
    assert summary['trials'] == 1 and summary['stop_reason'] == 'trial_cap'
    if condition == 'researcher_alone':
        assert [r for r, _, _ in model.observed] == ['researcher']
        assert framed == []
        assert model.observed[0][1].get('initial_framing') is None
    else:
        assert [r for r, _, _ in model.observed] == ['supervisor', 'researcher']
        assert model.observed[0][2] == []  # No experiment or literature tools at kickoff.
        assert 'model' in model.observed[0][1]['permitted_experiments']['properties']
        assert 'intent' not in model.observed[0][1]['permitted_experiments']['properties']
        assert len(framed) == 1 and framed[0]['after_trial'] == 0
        assert framed[0]['contract']['evidence'] == []
        first = model.observed[1][1]
        assert first['initial_framing'] == framed[0]['contract']
        assert first['last_supervisor_feedback'] == framed[0]['contract']
        assert first['active_advice_source'] == 'initial_framing'
        decision = next(e['contract'] for e in events if e['type'] == 'decision_contract' and e['valid'])
        assert decision['supervisor_response'] != 'not_applicable'
        assert summary['accounting']['calls'] == 2
        assert events.index(framed[0]) < next(i for i, e in enumerate(events) if e['type'] == 'trial_started')
    assert not any(e['type'] == 'review' for e in events)


def test_initial_framing_survives_later_reviews_and_history_truncation(tmp_path):
    model = ObservedModel()
    run_dir = tmp_path / 'run'
    result = asyncio.run(run_one(StudyConfig(condition='frequent', trial_cap=4, history_trials=1),
        tmp_path, run_dir, model, trial_runner=trial, project={}))
    events = [json.loads(line) for line in (run_dir / 'events.jsonl').read_text().splitlines()]
    kickoff = next(e['contract'] for e in events if e['type'] == 'framing')
    reviews = [e for e in events if e['type'] == 'review']
    assert [e['after_trial'] for e in reviews] == [1, 2, 3]
    final_context = model.observed[-1][1]
    assert final_context['initial_framing'] == kickoff
    assert final_context['last_supervisor_feedback'] == {
        key: value for key, value in reviews[-1]['contract'].items() if key != 'lesson_updates'}
    assert final_context['lessons'] and 'lesson_updates' not in final_context['last_supervisor_feedback']
    assert final_context['recent_trials'][0]['trial_id'] == 3
    (run_dir / 'summary.json').unlink()
    (run_dir / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events if e['type'] != 'run_stopped'))
    recovered = recover_run(run_dir)
    assert recovered['accounting'] == result['accounting']


def test_offline_supervisor_uses_retained_best_when_recent_attempts_all_failed(tmp_path):
    attempts = 0
    async def intermittent(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts in (2, 3):
            return {'status': 'failed', 'error': 'The bounded fit failed.'}
        return await trial(*args, **kwargs)
    run_dir = tmp_path / 'run'
    result = asyncio.run(run_one(StudyConfig(condition='periodic', trial_cap=4, history_trials=1),
        tmp_path, run_dir, FakeModel(), trial_runner=intermittent, project={}))
    assert result['stop_reason'] == 'trial_cap' and result['trials'] == 4
    events = [json.loads(line) for line in (run_dir / 'events.jsonl').read_text().splitlines()]
    feedback = next(e['contract'] for e in events if e['type'] == 'review')
    assert feedback['evidence'] == [{'trial_id': 1, 'metric': 'roc_auc', 'split': 'validation', 'value': .9}]


@pytest.mark.parametrize('failure', ['invalid_contract', 'dollar_cap', 'deadline'])
def test_kickoff_failure_or_exhausted_budget_cannot_start_training(tmp_path, monkeypatch, failure):
    from study import controller
    from types import SimpleNamespace
    clock = [100.0]
    monkeypatch.setattr(controller, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    class Blocked(ObservedModel):
        async def complete(self, messages, tools, *, timeout):
            response = await super().complete(messages, tools, timeout=timeout)
            if messages[0]['content'].startswith('ROLE: supervisor'):
                if failure == 'invalid_contract':
                    response['message'] = {'role': 'assistant', 'content': '{}'}
                elif failure == 'dollar_cap':
                    response['usage']['cost'] = 1
                else:
                    clock[0] += 60
            return response
    model = Blocked()
    result = asyncio.run(run_one(StudyConfig(condition='frequent', trial_cap=1,
        allowance_seconds=60, dollar_cap=1, review_tool_calls=1), tmp_path, tmp_path / 'run',
        model, trial_runner=trial, project={}))
    assert result['stop_reason'] == failure and result['trials'] == 0
    assert all(role == 'supervisor' for role, _, _ in model.observed)
    assert result['accounting']['calls'] == (2 if failure == 'invalid_contract' else 1)


def test_kickoff_and_review_fields_are_visible_in_live_narrative_and_report(tmp_path):
    from study.findings import Findings
    from study.focus import narrative
    from study.report import build_report_data
    state = Findings()
    narratives = []
    def observe(event):
        state.update(event)
        if event['type'] in ('framing', 'review'):
            narratives.append(narrative(state))
    asyncio.run(run_one(StudyConfig(condition='frequent', trial_cap=2), tmp_path,
        tmp_path / 'run', FakeModel(), trial_runner=trial, project={}, progress=observe))
    heading, rows, _ = narratives[0]
    assert heading == 'Supervisor framing'
    assert {label for label, _, _ in rows} >= {'Rationale (unverified)', 'Hypothesis', 'Open question'}
    heading, rows, _ = narratives[1]
    assert heading == 'Supervisor advice after trial 1'
    assert {label for label, _, _ in rows} >= {
        'Hypotheses', 'Analogy (unverified)', 'Would weaken it', 'Resource limits', 'Rationale (unverified)'}
    row = build_report_data(tmp_path / 'run')['runs'][0]
    framing = next(e for e in row['trace'] if e['type'] == 'framing')
    assert framing['contract']['motivation'] and framing['contract']['hypothesis']
    assert next(e for e in row['trace'] if e['type'] == 'review')['contract']['resource_check']
    assert 'supervisor framing' in (tmp_path / 'run/progress.log').read_text()


def test_reports_separate_historical_supervision_from_new_policy():
    from study.report_analysis import assign_analysis_groups
    config = StudyConfig()
    assert config.to_dict()['supervisor_policy'] == 'supervision_v2'
    historical = {'condition': 'frequent', 'config': {'decision_protocol': 'structured_v1'}}
    current = copy.deepcopy(historical)
    current['config']['supervisor_policy'] = 'supervision_v2'
    assign_analysis_groups([historical, current])
    assert historical['analysis_group'] != current['analysis_group']
