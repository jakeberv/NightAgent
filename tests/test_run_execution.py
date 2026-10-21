"""Exercise focused run dependencies with a controlled clock and no API calls."""
import asyncio
from copy import deepcopy
import json

import pytest

from study.config import StudyConfig
from study.model_calls import ModelCalls
from study.problem import legacy_problem
from study.reasoning import LessonMemory
from study.run_context import build_context
from study.run_state import RunState, StopRun
from study.trial_execution import TrialExecutor


class RecordingJournal:
    def __init__(self):
        self.events = []

    def emit(self, event_type, **payload):
        self.events.append(deepcopy({'type': event_type, **payload}))


def make_state(**overrides):
    clock = [100.0]
    state = RunState(StudyConfig(**overrides), legacy_problem(), clock=lambda: clock[0])
    return state, clock


def test_state_uses_one_clock_and_keeps_run_mutations_local():
    state, clock = make_state(allowance_seconds=30)
    other, _ = make_state(allowance_seconds=30)
    state.history.append({'trial_id': 1})
    state.call_durations['researcher'] = [2]
    state.summary['trials'] = 1
    clock[0] += 29
    assert state.remaining() == 1
    state.check()
    clock[0] += 1
    with pytest.raises(StopRun, match='deadline'):
        state.check()
    assert other.history == [] and other.call_durations == {}
    assert other.summary['trials'] == 0 and other.accounting.calls == 0


@pytest.mark.parametrize('overrides,mutation,reason', [
    ({}, lambda state: state.accounting.add(None), 'unknown_cost'),
    ({'dollar_cap': .01}, lambda state: state.accounting.add({'cost': .01}), 'dollar_cap'),
    ({'trial_cap': 1}, lambda state: state.summary.update(trials=1), 'trial_cap'),
])
def test_state_safeguards_are_enforced_before_more_work(overrides, mutation, reason):
    state, _ = make_state(**overrides)
    mutation(state)
    with pytest.raises(StopRun, match=reason):
        state.check()


@pytest.mark.parametrize('role', ['researcher', 'supervisor', 'reflection'])
def test_context_preserves_old_evidence_outside_recent_window_and_role_fields(role):
    state, _ = make_state(condition='periodic_reflection', history_trials=1)
    state.history.extend([
        {'trial_id': 1, 'status': 'completed', 'metrics': {'roc_auc': .9, 'bad': None}},
        {'trial_id': 2, 'status': 'failed', 'error': 'fit failed'},
        {'trial_id': 3, 'status': 'completed', 'metrics': {'roc_auc': .91}},
    ])
    state.summary['trials'] = 3
    state.initial_framing = state.feedback = {'summary': 'Initial advice.', 'lesson_updates': []}
    state.reflection = {'summary': 'A measured reflection.', 'lesson_updates': []}
    context = json.loads(build_context(state, project={'name': 'fixture'},
        permitted_experiments={'type': 'object'}, memory=LessonMemory(6), role=role))
    assert [row['trial_id'] for row in context['recent_trials']] == [3]
    assert context['evidence_metrics_by_trial'] == {'1': ['roc_auc'], '3': ['roc_auc']}
    assert context['active_advice_source'] == 'initial_framing'
    assert context['last_supervisor_feedback'] == {'summary': 'Initial advice.'}
    assert context['last_explicit_reflection'] == {'summary': 'A measured reflection.'}
    assert ('permitted_experiments' in context) == (role != 'researcher')
    assert ('supervisor_stage' in context) == (role == 'supervisor')
    assert context['lessons'] == []


def test_model_retry_refreshes_context_and_accounts_each_attempt():
    state, clock = make_state(allowance_seconds=30)
    journal = RecordingJournal()
    contexts = []

    class ProviderError(Exception):
        details = {'usage': {'cost': .02, 'prompt_tokens': 2, 'completion_tokens': 0}}

    class Model:
        async def complete(self, messages, tools, *, timeout):
            contexts.append(json.loads(messages[1]['content']))
            if len(contexts) == 1:
                clock[0] += 3
                raise ProviderError('retryable')
            clock[0] += 2
            return {'message': {'role': 'assistant', 'content': 'accepted'},
                    'usage': {'cost': .01, 'prompt_tokens': 2, 'completion_tokens': 1}}

    context = lambda role, framing=False: json.dumps({'remaining_seconds': state.remaining()})
    calls = ModelCalls(state=state, journal=journal, model=Model(), context=context)
    result = asyncio.run(calls('researcher', [{'role': 'system', 'content': 'rules'},
        {'role': 'user', 'content': 'stale'}], []))
    assert result['content'] == 'accepted'
    assert [row['remaining_seconds'] for row in contexts] == [30, 27]
    assert state.accounting.calls == 2 and state.accounting.known_cost == pytest.approx(.03)
    assert state.model_seconds == 5 and state.call_durations == {'researcher': [2]}
    assert [(event['type'], event.get('status')) for event in journal.events] == [
        ('model_call_started', None), ('model_call', 'failed'),
        ('model_call_started', None), ('model_call', 'completed')]


def test_model_admission_does_not_call_or_charge_provider():
    state, clock = make_state(allowance_seconds=30)
    clock[0] += 29.5
    journal = RecordingJournal()
    calls = ModelCalls(state=state, journal=journal, model=None, context=None)
    with pytest.raises(StopRun, match='deadline'):
        asyncio.run(calls('researcher', [], []))
    assert state.accounting.calls == 0
    assert [row['type'] for row in journal.events] == ['model_call_skipped']


def test_model_cancellation_is_recorded_with_unknown_charge():
    state, clock = make_state()
    journal = RecordingJournal()

    class Model:
        async def complete(self, *args, **kwargs):
            clock[0] += 2
            raise asyncio.CancelledError()

    calls = ModelCalls(state=state, journal=journal, model=Model(),
                       context=lambda *args, **kwargs: '{}')
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(calls('researcher', [{}, {}], []))
    assert state.accounting.calls == 1 and not state.accounting.cost_complete
    assert state.model_seconds == 2
    assert journal.events[-1]['status'] == 'cancelled'


@pytest.mark.parametrize('outcome', ['completed', 'timeout', 'failed', 'late'])
def test_trial_executor_records_result_before_selection_and_checkpoint(tmp_path, outcome):
    state, clock = make_state(allowance_seconds=30)
    journal = RecordingJournal()
    arguments = {'model': 'logistic', 'preprocessing': 'standard', 'params': {}}
    diagnostic = {'effective_config': {'model': 'logistic'}, 'fingerprint': 'fixture',
                  'provenance': {}, 'equivalent_trial_ids': [], 'warning': None}

    async def fit(data_dir, trial_dir, config, *, seed, timeout):
        assert trial_dir == tmp_path / 'trials' / '0001'
        assert config == arguments and seed == 42 and timeout == 30
        clock[0] += 31 if outcome == 'late' else 4
        if outcome == 'timeout':
            raise TimeoutError()
        if outcome == 'failed':
            raise ValueError('fit failed')
        return {'status': 'completed', 'score': .96, 'metrics': {'roc_auc': .96},
                'artifact': 'fixture', 'artifact_hash': 'fixture'}

    executor = TrialExecutor(state=state, journal=journal, trial_runner=fit,
                             data_dir=tmp_path, run_dir=tmp_path)
    result = asyncio.run(executor.execute(arguments, diagnostic, intent={}, message={}))
    assert result['status'] == outcome and result['trial_id'] == 1
    assert state.summary['trials'] == 1 and state.history[-1]['status'] == outcome
    assert state.summary['training_seconds'] == (31 if outcome == 'late' else 4)
    assert (state.summary['best'] is not None) == (outcome == 'completed')
    assert json.loads((tmp_path / 'checkpoint.json').read_text()) == state.summary
    assert [row['type'] for row in journal.events] == [
        'decision', 'experiment_diagnostic', 'trial_started', 'trial_finished', 'selection']
    assert 'artifact' not in result
    if outcome in ('completed', 'late'):
        assert state.history[-1]['artifact'] == 'fixture'
