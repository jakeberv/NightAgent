"""Terminal repairs and novelty bookkeeping stay truthful without paid calls."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from study import controller
from study.config import StudyConfig
from study.diagnostics import describe_experiment
from study.fake import FakeModel, scripted_contract
from study.problem import legacy_problem, load_problem
from study.reasoning import LessonMemory
from study.run_context import build_context
from study.run_state import RunState


def recorded(trial_id, config, *, problem=None, seed=42, status='completed', project=None):
    return {'trial_id': trial_id, 'status': status, 'seed': seed, 'config': copy.deepcopy(config),
            'metrics': {'roc_auc': .8}, 'score': .8,
            'artifact': 'large-irrelevant-artifact', 'artifact_hash': 'ignored',
            **describe_experiment(config, problem=problem,
                                  project=project or {'n_features': 10}, seed=seed)}


def context_with(history, *, memory=False, problem=None, project=None):
    problem = problem or legacy_problem()
    state = RunState(StudyConfig(history_trials=12, lesson_memory=memory), problem, clock=lambda: 0)
    state.history.extend(history)
    state.summary.update(trials=len(history), best=history[-1] if history else None)
    return json.loads(build_context(state, project=project or {'n_features': 10},
        permitted_experiments={}, memory=LessonMemory(), role='researcher'))


def expanded(registry, entry):
    return registry['parameter_bases'][entry['model']] | entry['params']


def test_completed_registry_retains_old_aliases_defaults_and_seeds_without_lesson_memory():
    forest = {'model': 'random_forest', 'preprocessing': 'none', 'params': {'max_features': 'sqrt'}}
    history = [recorded(1, forest), recorded(2, forest | {'params': {'max_features': 'log2'}})]
    history += [recorded(i, {'model': 'logistic', 'preprocessing': 'standard', 'params': {'C': i}})
                for i in range(3, 17)]
    history += [recorded(17, forest, seed=43), recorded(18, forest, status='failed')]
    context = context_with(history)
    assert 'lessons' not in context
    assert all(row['trial_id'] > 2 for row in context['recent_trials'])
    registry = context['completed_configurations']
    entries = registry['entries']
    original = next(entry for entry in entries if entry['trial_ids'] == [1, 2])
    assert original['seed'] == 42
    assert expanded(registry, original)['max_features'] == 3
    assert expanded(registry, original)['n_estimators'] == 100
    assert any(entry['trial_ids'] == [17] and entry['seed'] == 43 for entry in entries)
    assert {trial_id for entry in entries for trial_id in entry['trial_ids']} == set(range(1, 18))
    encoded = json.dumps(registry)
    assert all(f'"{name}":' not in encoded for name in
               ('artifact', 'fingerprint', 'provenance', 'metrics', 'random_state', 'n_jobs'))


def test_cnn_registry_uses_resolved_inactive_defaults_instead_of_old_request_spelling():
    problem = load_problem('study/problems/fashion-mnist.yaml')
    cnn = {'model': 'torch_cnn', 'preprocessing': 'none', 'params': {}}
    history = [recorded(i, cnn, problem=problem, project={'n_features': 784}) for i in (1, 2)]
    # Old proposals mentioned this inactive CNN knob; actual constructor science
    # still used 64. Repeating those spellings must not invent novel configs.
    history[0]['config']['params']['hidden_width'] = 128
    history[1]['config']['params']['hidden_width'] = 256
    registry = context_with(history, problem=problem, project={'n_features': 784})['completed_configurations']
    assert len(registry['entries']) == 1
    entry = registry['entries'][0]
    assert entry['trial_ids'] == [1, 2]
    assert expanded(registry, entry)['hidden_width'] == 64
    assert expanded(registry, entry)['channels'] == 16
    assert expanded(registry, entry)['batch_size'] == 128


def test_registry_compacts_one_thousand_completed_trials_without_dropping_novelty():
    config = {'model': 'logistic', 'preprocessing': 'standard', 'params': {}}
    history = [recorded(i, config | {'params': {'C': (i + 1) / 20}}) for i in range(1, 1001)]
    registry = context_with(history)['completed_configurations']
    assert len(registry['entries']) == 1000
    assert {i for entry in registry['entries'] for i in entry['trial_ids']} == set(range(1, 1001))
    assert expanded(registry, registry['entries'][0])['C'] == .1
    assert expanded(registry, registry['entries'][-1])['C'] == 50.05
    assert len(json.dumps(registry)) < 150_000
    assert 'artifact' not in json.dumps(registry)


async def fit(data, output, config, *, seed, timeout):
    return {'status': 'completed', 'score': .9, 'metrics': {'roc_auc': .9},
            'artifact': 'fixture', 'artifact_hash': str(output)}


def events_in(path):
    return [json.loads(line) for line in (path / 'events.jsonl').read_text().splitlines()]


@pytest.mark.parametrize('memory', [False, True])
def test_reuse_feedback_persists_across_review_reflection_and_research_phases(tmp_path, memory):
    class NoveltyAware(FakeModel):
        def __init__(self):
            super().__init__()
            self.contexts = []
            self.research_calls = 0

        async def complete(self, messages, tools, *, timeout):
            role = messages[0]['content'].splitlines()[0].removeprefix('ROLE: ')
            context = json.loads(messages[1]['content'])
            self.contexts.append((role, copy.deepcopy(context)))
            if role != 'researcher':
                return await super().complete(messages, tools, timeout=timeout)
            self.research_calls += 1
            if self.research_calls <= 2:
                config = {'model': 'random_forest', 'preprocessing': 'none',
                          'params': {'max_features': 'sqrt' if self.research_calls == 1 else 'log2'}}
            elif context.get('last_reused_proposal', {}).get('matched_trial_ids') == [1]:
                # The agent explicitly chooses a meaningful alternative using
                # the feedback; the harness must never substitute it itself.
                config = {'model': 'logistic', 'preprocessing': 'standard',
                          'params': {'C': context['trials_attempted'] + 1}}
            else:
                config = {'model': 'random_forest', 'preprocessing': 'none', 'params': {'max_features': 'log2'}}
            return {'message': {'role': 'assistant', 'content': '', 'tool_calls': [{
                'id': f'choose-{self.research_calls}', 'type': 'function', 'function': {
                    'name': 'run_analysis', 'arguments': json.dumps(config | {
                        'intent': scripted_contract('researcher', context)})}}]},
                'usage': {'prompt_tokens': 10, 'completion_tokens': 2, 'cost': 0}}

    model = NoveltyAware()
    result = asyncio.run(controller.run_one(StudyConfig(condition='periodic_reflection',
        lesson_memory=memory, trial_cap=4, history_trials=1, max_turns_without_trial=3),
        tmp_path, tmp_path / 'run', model, trial_runner=fit, project={'n_features': 10}))
    assert result['stop_reason'] == 'trial_cap' and result['trials'] == 4
    events = events_in(tmp_path / 'run')
    started = [event for event in events if event['type'] == 'trial_started']
    assert [event['config']['model'] for event in started] == ['random_forest', 'logistic', 'logistic', 'logistic']
    assert len([event for event in events if event['type'] == 'experiment_reused']) == 1
    assert [event['trial_id'] for event in started] == [1, 2, 3, 4]
    later = [(role, context) for role, context in model.contexts if context['trials_attempted'] >= 2]
    assert {'researcher', 'supervisor', 'reflection'} <= {role for role, context in later}
    assert all(context['last_reused_proposal']['matched_trial_ids'] == [1] for role, context in later)
    assert all(context['reused_proposals'] == 1 for role, context in later)
    assert all(any(1 in entry['trial_ids'] for entry in context['completed_configurations']['entries'])
               for role, context in later)
    if not memory:
        assert all('lessons' not in context for role, context in model.contexts)
        assert 'lessons' not in result
        assert not any(event['type'] == 'lesson_memory' for event in events)


def test_repeated_reuse_uses_existing_no_progress_bound_and_failed_fit_can_retry(tmp_path):
    async def failed_once(data, output, config, *, seed, timeout):
        if output.name == '0001':
            return {'status': 'failed', 'error': 'temporary worker failure'}
        return await fit(data, output, config, seed=seed, timeout=timeout)

    model = FakeModel([{'model': 'logistic', 'preprocessing': 'standard', 'params': {}}])
    result = asyncio.run(controller.run_one(StudyConfig(trial_cap=3, max_turns_without_trial=3),
        tmp_path, tmp_path / 'run', model, trial_runner=failed_once, project={}))
    events = events_in(tmp_path / 'run')
    assert result['stop_reason'] == 'no_progress' and result['trials'] == 2
    assert result['accounting']['calls'] == 5
    assert len([e for e in events if e['type'] == 'trial_started']) == 2
    reuses = [event for event in events if event['type'] == 'experiment_reused']
    assert len(reuses) == 3 and all(event['matched_trial_ids'] == [2] for event in reuses)


@pytest.mark.parametrize('role,condition', [('supervisor', 'frequent'), ('reflection', 'periodic_reflection')])
def test_pending_invalid_review_is_durably_abandoned_only_when_repair_admission_fails(tmp_path, monkeypatch, role, condition):
    clock = [100.]
    monkeypatch.setattr(controller, 'time', SimpleNamespace(monotonic=lambda: clock[0]))

    class InvalidAtDeadline(FakeModel):
        async def complete(self, messages, tools, *, timeout):
            context = json.loads(messages[1]['content'])
            active = messages[0]['content'].splitlines()[0].removeprefix('ROLE: ')
            if active == role and context['trials_attempted'] > 0:
                contract = scripted_contract(role, context)
                contract['summary'] = 'x' * 241
                # A rejected contract must never update advice or lesson memory.
                if 'lesson_updates' in contract:
                    contract['lesson_updates'][0]['id'] = 'invalid-terminal-lesson'
                clock[0] = 159.6
                return {'message': {'role': 'assistant', 'content': json.dumps(contract)},
                        'usage': {'prompt_tokens': 2, 'completion_tokens': 2, 'cost': .01}}
            return await super().complete(messages, tools, timeout=timeout)

    result = asyncio.run(controller.run_one(StudyConfig(condition=condition, trial_cap=2, allowance_seconds=60),
        tmp_path, tmp_path / 'run', InvalidAtDeadline(), trial_runner=fit, project={}))
    events = events_in(tmp_path / 'run')
    assert result['stop_reason'] == 'deadline' and result['trials'] == 1
    invalid = next(e for e in events if e['type'] == role + '_contract' and not e['valid'])
    abandonment = next(e for e in events if e['type'] == 'contract_abandoned')
    assert {key: abandonment[key] for key in ('role', 'after_trial', 'stage', 'reason')} == {
        'role': role, 'after_trial': 1, 'stage': 'review', 'reason': 'deadline_admission'}
    assert abandonment['contract'] == invalid['contract'] and abandonment['errors'] == invalid['errors']
    index = events.index(abandonment)
    assert events[index - 1]['type'] == 'model_call_skipped'
    assert [event['type'] for event in events[index + 1:]] == ['run_stopped']
    assert all(lesson['id'] != 'invalid-terminal-lesson' for lesson in result['lessons'])
    assert not any(e['type'] in ('review', 'reflection') for e in events)
    assert result['accounting']['cost_complete']


@pytest.mark.parametrize('framing', [False, True])
def test_unrepaired_contract_with_available_budget_remains_a_real_error(tmp_path, framing):
    class Invalid(FakeModel):
        async def complete(self, messages, tools, *, timeout):
            context = json.loads(messages[1]['content'])
            if messages[0]['content'].startswith('ROLE: supervisor') and (framing or context['trials_attempted']):
                return {'message': {'role': 'assistant', 'content': '{}'},
                        'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'cost': 0}}
            return await super().complete(messages, tools, timeout=timeout)

    result = asyncio.run(controller.run_one(StudyConfig(condition='frequent', trial_cap=2, review_tool_calls=1),
        tmp_path, tmp_path / 'run', Invalid(), trial_runner=fit, project={}))
    assert result['stop_reason'] == 'invalid_contract'
    assert result['trials'] == (0 if framing else 1)
    assert not any(e['type'] == 'contract_abandoned' for e in events_in(tmp_path / 'run'))


def test_registry_groups_seeded_legacy_aliases_with_native_metadata_but_marks_unknown_seed():
    forest = {'model': 'random_forest', 'preprocessing': 'none', 'params': {'max_features': 'sqrt'}}
    history = [recorded(1, forest),
               {'trial_id': 2, 'status': 'completed', 'seed': 42,
                'config': forest | {'params': {'max_features': 'log2'}}},
               {'trial_id': 3, 'status': 'completed', 'config': forest}]
    registry = context_with(history, project={'n_features': 10, 'constructor': 'legacy'})['completed_configurations']
    assert len(registry['entries']) == 1
    assert registry['entries'][0]['trial_ids'] == [1, 2]
    assert registry['unresolved_trials'] == [{'trial_id': 3, 'config': forest, 'seed': None}]


def test_invalid_initial_framing_abandoned_at_deadline_never_authorizes_a_fit(tmp_path, monkeypatch):
    clock = [100.]
    monkeypatch.setattr(controller, 'time', SimpleNamespace(monotonic=lambda: clock[0]))

    class InvalidFraming(FakeModel):
        async def complete(self, messages, tools, *, timeout):
            clock[0] = 159.6
            return {'message': {'role': 'assistant', 'content': '{}'},
                    'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'cost': 0}}

    result = asyncio.run(controller.run_one(StudyConfig(condition='frequent', allowance_seconds=60),
        tmp_path, tmp_path / 'run', InvalidFraming(), trial_runner=fit, project={}))
    events = events_in(tmp_path / 'run')
    assert result['stop_reason'] == 'deadline' and result['trials'] == 0 and result['best'] is None
    assert next(event for event in events if event['type'] == 'contract_abandoned')['stage'] == 'framing'
    assert not any(event['type'] in ('framing', 'trial_started', 'lesson_memory') for event in events)


def test_deadline_during_a_started_repair_is_not_claimed_as_admission_abandonment(tmp_path, monkeypatch):
    clock = [100.]
    monkeypatch.setattr(controller, 'time', SimpleNamespace(monotonic=lambda: clock[0]))

    class ExpiringRepair(FakeModel):
        reviews = 0
        async def complete(self, messages, tools, *, timeout):
            context = json.loads(messages[1]['content'])
            if messages[0]['content'].startswith('ROLE: supervisor') and context['trials_attempted']:
                self.reviews += 1
                if self.reviews == 2:
                    clock[0] = 160.
                return {'message': {'role': 'assistant', 'content': '{}'},
                        'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'cost': 0}}
            return await super().complete(messages, tools, timeout=timeout)

    result = asyncio.run(controller.run_one(StudyConfig(condition='frequent', allowance_seconds=60),
        tmp_path, tmp_path / 'run', ExpiringRepair(), trial_runner=fit, project={}))
    events = events_in(tmp_path / 'run')
    assert result['stop_reason'] == 'deadline' and result['trials'] == 1
    assert any(event['type'] == 'supervisor_contract' and not event['valid'] for event in events)
    assert not any(event['type'] in ('contract_abandoned', 'model_call_skipped', 'review') for event in events)
