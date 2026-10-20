import asyncio
import json
import pytest

from study.config import StudyConfig
from study.controller import run_one, recover_run
from test_reasoning import decision


async def trial(data_dir, trial_dir, config, *, seed, timeout):
    assert 'intent' not in config
    return {'status': 'completed', 'validation_auc': .9, 'metrics': {'roc_auc': .9},
            'artifact': 'fake', 'artifact_hash': str(trial_dir)}


class StructuredModel:
    def __init__(self, *, invalid_first=False, memory=False):
        self.contexts = []
        self.invalid_first = invalid_first
        self.calls = 0
        self.memory = memory

    async def complete(self, messages, tools, *, timeout):
        self.calls += 1
        context = json.loads(messages[1]['content'])
        self.contexts.append(context)
        latest = context['trials_attempted']
        contract = decision()
        contract['baseline_trial_id'] = latest or None
        contract['evidence'] = ([{'trial_id': latest, 'metric': 'roc_auc', 'split': 'validation', 'value': .9}]
                                if latest else [])
        if self.invalid_first and self.calls == 1:
            contract['evidence'] = [{'trial_id': 999, 'metric': 'roc_auc', 'split': 'validation', 'value': .9}]
        if self.memory and latest == 1:
            contract['lesson_updates'] = [{'id': 'baseline', 'status': 'supported',
                'summary': 'The initial baseline achieved validation AUC 0.9.',
                'scope': 'This observation applies to this run and split.', 'evidence': contract['evidence']}]
        return {'message': {'role': 'assistant', 'tool_calls': [{'id': str(self.calls), 'type': 'function',
            'function': {'name': 'run_analysis', 'arguments': json.dumps({
                'model': 'logistic', 'preprocessing': 'standard', 'params': {}, 'intent': contract})}}]},
            'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'cost': .001}}


def test_bad_evidence_repairs_within_existing_budget_before_training(tmp_path):
    model = StructuredModel(invalid_first=True)
    result = asyncio.run(run_one(StudyConfig(decision_protocol='structured_v1', trial_cap=2),
        tmp_path, tmp_path / 'run', model, trial_runner=trial, project={'feature_names': ['a'] * 10}))
    assert result['trials'] == 2 and model.calls == 3
    events = [json.loads(line) for line in (tmp_path / 'run/events.jsonl').read_text().splitlines()]
    contracts = [event for event in events if event['type'] == 'decision_contract']
    assert [event['valid'] for event in contracts] == [False, True, True]
    assert any(event['type'] == 'experiment_diagnostic' and event['equivalent_trial_ids'] == [1] for event in events)
    assert result['accounting']['calls'] == 3


def test_memory_is_run_local_survives_history_window_and_recovers(tmp_path):
    model = StructuredModel(memory=True)
    config = StudyConfig(decision_protocol='structured_v1', lesson_memory=True, trial_cap=4, history_trials=1)
    result = asyncio.run(run_one(config, tmp_path, tmp_path / 'run', model, trial_runner=trial, project={}))
    assert model.contexts[0]['lessons'] == []
    assert model.contexts[-1]['recent_trials'][0]['trial_id'] == 3
    assert model.contexts[-1]['lessons'][0]['evidence'][0]['trial_id'] == 1
    assert result['lessons'][0]['id'] == 'baseline'
    (tmp_path / 'run/summary.json').unlink()
    events_path = tmp_path / 'run/events.jsonl'
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    events_path.write_text(''.join(json.dumps(event) + '\n' for event in events if event['type'] != 'run_stopped'))
    assert recover_run(tmp_path / 'run')['lessons'] == result['lessons']
    other = StructuredModel()
    asyncio.run(run_one(StudyConfig(trial_cap=1, decision_protocol='structured_v1'), tmp_path,
        tmp_path / 'other', other, trial_runner=trial, project={}))
    assert 'lessons' not in other.contexts[0]


def test_invalid_review_is_not_accepted_as_feedback(tmp_path):
    class Reviewer(StructuredModel):
        async def complete(self, messages, tools, *, timeout):
            if messages[0]['content'].startswith('ROLE: supervisor'):
                return {'message': {'role': 'assistant', 'content': 'An unsupported fragment'},
                        'usage': {'prompt_tokens': 2, 'completion_tokens': 2, 'cost': 0}}
            return await super().complete(messages, tools, timeout=timeout)
    result = asyncio.run(run_one(StudyConfig(condition='frequent', decision_protocol='structured_v1',
        review_tool_calls=1, trial_cap=2), tmp_path, tmp_path / 'run', Reviewer(), trial_runner=trial, project={}))
    assert result['stop_reason'] == 'invalid_contract'
    assert result['trials'] == 1


def test_default_offline_model_exercises_all_contract_roles_and_optional_memory(tmp_path):
    from study.fake import FakeModel
    model = FakeModel()
    result = asyncio.run(run_one(StudyConfig(condition='periodic_reflection', lesson_memory=True,
        trial_cap=4), tmp_path, tmp_path / 'run', model, trial_runner=trial, project={}))
    assert result['stop_reason'] == 'trial_cap' and result['trials'] == 4
    assert result['lessons']
    events = [json.loads(line) for line in (tmp_path / 'run/events.jsonl').read_text().splitlines()]
    assert all(event['valid'] for event in events if event['type'].endswith('_contract'))
    assert sum(event['type'] == 'review' for event in events) == 1
    assert sum(event['type'] == 'reflection' for event in events) == 3


@pytest.mark.parametrize('number', ['NaN', 'Infinity', '1e309', '1' + '0' * 310])
def test_nonfinite_review_citation_is_repaired_without_crashing_journal(tmp_path, number):
    from study.fake import FakeModel, scripted_contract
    class Reviewer(FakeModel):
        attempts = 0
        async def complete(self, messages, tools, *, timeout):
            if messages[0]['content'].startswith('ROLE: supervisor'):
                self.attempts += 1
                context = json.loads(messages[1]['content'])
                contract = scripted_contract('supervisor', context)
                content = json.dumps(contract)
                if self.attempts == 1:
                    content = content.replace('"value": 0.9', '"value": ' + number)
                return {'message': {'role': 'assistant', 'content': content},
                        'usage': {'prompt_tokens': 2, 'completion_tokens': 2, 'cost': 0}}
            return await super().complete(messages, tools, timeout=timeout)
    model = Reviewer()
    result = asyncio.run(run_one(StudyConfig(condition='frequent', trial_cap=2),
        tmp_path, tmp_path / 'run', model, trial_runner=trial, project={}))
    assert result['stop_reason'] == 'trial_cap'
    assert model.attempts == 2
    events = [json.loads(line) for line in (tmp_path / 'run/events.jsonl').read_text().splitlines()]
    assert [e['valid'] for e in events if e['type'] == 'supervisor_contract'] == [False, True]


def test_missing_intent_is_logged_as_invalid_before_repair(tmp_path):
    class MissingIntent(StructuredModel):
        async def complete(self, messages, tools, *, timeout):
            response = await super().complete(messages, tools, timeout=timeout)
            if self.calls == 1:
                function = response['message']['tool_calls'][0]['function']
                arguments = json.loads(function['arguments'])
                arguments.pop('intent')
                function['arguments'] = json.dumps(arguments)
            return response
    result = asyncio.run(run_one(StudyConfig(trial_cap=1), tmp_path, tmp_path / 'run',
        MissingIntent(), trial_runner=trial, project={}))
    assert result['stop_reason'] == 'trial_cap'
    events = [json.loads(line) for line in (tmp_path / 'run/events.jsonl').read_text().splitlines()]
    assert [e['valid'] for e in events if e['type'] == 'decision_contract'] == [False, True]


def test_review_repair_refreshes_budget_and_disables_unneeded_tools(tmp_path, monkeypatch):
    from study.fake import FakeModel, scripted_contract
    from study import controller
    from types import SimpleNamespace
    clock = [100.0]
    monkeypatch.setattr(controller, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    seen = []
    class Reviewer(FakeModel):
        async def complete(self, messages, tools, *, timeout):
            if messages[0]['content'].startswith('ROLE: supervisor'):
                context = json.loads(messages[1]['content'])
                seen.append((context, tools))
                contract = scripted_contract('supervisor', context)
                if len(seen) == 1:
                    contract['assessment'] = 'A long explanation ' * 50 + '.'
                    clock[0] += 10
                return {'message': {'role': 'assistant', 'content': json.dumps(contract)},
                        'usage': {'prompt_tokens': 2, 'completion_tokens': 2, 'cost': .01}}
            return await super().complete(messages, tools, timeout=timeout)
    result = asyncio.run(run_one(StudyConfig(condition='frequent', trial_cap=2, allowance_seconds=60),
        tmp_path, tmp_path / 'run', Reviewer(), trial_runner=trial, project={}))
    assert result['stop_reason'] == 'trial_cap'
    assert seen[0][0]['remaining_seconds'] - seen[1][0]['remaining_seconds'] == 10
    assert seen[1][0]['remaining_trials'] == 1
    assert seen[1][0]['mean_model_call_seconds'] > 0
    assert seen[0][1] and seen[1][1] == []


def test_subsecond_review_retry_is_skipped_without_unknown_charge(tmp_path, monkeypatch):
    from study.fake import FakeModel
    from study import controller
    from types import SimpleNamespace
    clock = [100.0]
    monkeypatch.setattr(controller, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    class Reviewer(FakeModel):
        reviews = 0
        async def complete(self, messages, tools, *, timeout):
            if messages[0]['content'].startswith('ROLE: supervisor'):
                self.reviews += 1
                clock[0] = 159.6
                return {'message': {'role': 'assistant', 'content': 'Invalid review.'},
                        'usage': {'prompt_tokens': 2, 'completion_tokens': 2, 'cost': .01}}
            return await super().complete(messages, tools, timeout=timeout)
    model = Reviewer()
    result = asyncio.run(run_one(StudyConfig(condition='frequent', trial_cap=2, allowance_seconds=60),
        tmp_path, tmp_path / 'run', model, trial_runner=trial, project={}))
    assert result['stop_reason'] == 'deadline' and model.reviews == 1
    assert result['accounting']['cost_complete'] and result['accounting']['calls'] == 2
    assert result['best']['trial_id'] == 1
    events = [json.loads(line) for line in (tmp_path / 'run/events.jsonl').read_text().splitlines()]
    skipped = [e for e in events if e['type'] == 'model_call_skipped']
    assert len(skipped) == 1 and skipped[0]['remaining_seconds'] == pytest.approx(.4)
    assert 'model call skipped' in (tmp_path / 'run/progress.log').read_text()


def test_researcher_tool_schema_uses_compact_multi_field_repairs(tmp_path):
    class LongIntent(StructuredModel):
        async def complete(self, messages, tools, *, timeout):
            response = await super().complete(messages, tools, timeout=timeout)
            if self.calls == 1:
                function = response['message']['tool_calls'][0]['function']
                args = json.loads(function['arguments'])
                args['intent'].update(summary='Long summary ' * 50 + '.',
                                      hypothesis='Long hypothesis ' * 50 + '.')
                function['arguments'] = json.dumps(args)
            return response
    model = LongIntent()
    result = asyncio.run(run_one(StudyConfig(trial_cap=1), tmp_path, tmp_path / 'run',
        model, trial_runner=trial, project={}))
    assert result['trials'] == 1 and model.calls == 2
    events = [json.loads(line) for line in (tmp_path / 'run/events.jsonl').read_text().splitlines()]
    invalid = next(e for e in events if e['type'] == 'decision_contract' and not e['valid'])
    error = ' '.join(invalid['errors'])
    assert 'intent.summary' in error and '240' in error
    assert 'intent.hypothesis' in error and '500' in error
    assert len(error) < 400
