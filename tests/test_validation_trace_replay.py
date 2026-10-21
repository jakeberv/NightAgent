"""Cardinality repairs replay the real terminal reflection without paid calls."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from study import controller
from study.config import StudyConfig
from study.fake import FakeModel
from study.reasoning import request_contract_schema, schema_errors
from test_reasoning_controller import trial


CASES = json.loads((Path(__file__).parent / 'fixtures/validation-feedback-failures.json').read_text())['cases']


@pytest.mark.parametrize('case', CASES, ids=['repeated_after_trial_19', 'terminal_after_trial_20'])
def test_live_excess_citations_feedback_names_exact_path_limit_and_count(case):
    errors = schema_errors(case['contract'], request_contract_schema('reflection', memory=True),
                           'reflection request')
    assert len(errors) == 1
    assert case['expected_path'] in errors[0]
    assert 'at most 6 items' in errors[0] and 'received 7' in errors[0]
    assert 'trial_id' not in errors[0]  # The actionable reason must not follow a dumped array.
    assert len(errors[0]) < 150


@pytest.mark.parametrize('keyword,limit,count,phrase', [
    ('maxItems', 6, 7, 'at most 6 items'),
    ('minItems', 1, 0, 'at least 1 item'),
])
def test_array_cardinality_feedback_is_compact_without_echoing_contents(keyword, limit, count, phrase):
    value = ['private-marker-' + 'x' * 1000] * count
    errors = schema_errors(value, {'type': 'array', keyword: limit}, 'test request')
    assert len(errors) == 1 and phrase in errors[0] and f'received {count}' in errors[0]
    assert 'private-marker' not in errors[0] and len(errors[0]) < 150


class CardinalityRepairModel(FakeModel):
    def __init__(self, clock=None):
        super().__init__([{'model': 'logistic', 'preprocessing': 'standard', 'params': {'C': i}}
                          for i in range(1, 9)])
        self.clock = clock
        self.bad_calls = 0

    async def complete(self, messages, tools, *, timeout):
        role = messages[0]['content'].splitlines()[0].removeprefix('ROLE: ')
        context = json.loads(messages[1]['content'])
        if role != 'reflection' or context['trials_attempted'] != 7:
            return await super().complete(messages, tools, timeout=timeout)
        self.bad_calls += 1
        contract = deepcopy(CASES[-1]['contract'])
        source_ids = [item['trial_id'] for item in contract['lesson_updates'][0]['evidence']]
        mapping = {source: index for index, source in enumerate(source_ids, 1)}
        for record in [contract, *contract['lesson_updates']]:
            record['evidence'] = [{'trial_id': mapping[item['trial_id']], 'metric': 'roc_auc'}
                                  for item in record['evidence']]
        contract['next_comparison'] = {'model': 'logistic', 'preprocessing': 'standard', 'params': {'C': 8}}
        feedback = '\n'.join(message.get('content', '') for message in messages if message['role'] == 'user')
        if 'at most 6 items' in feedback and 'received 7' in feedback:
            contract['lesson_updates'][0]['evidence'] = contract['lesson_updates'][0]['evidence'][:6]
        if self.clock is not None:
            self.clock[0] = 159.6
        return {'message': {'role': 'assistant', 'content': json.dumps(contract)},
                'usage': {'prompt_tokens': 2, 'completion_tokens': 2, 'cost': 0}}


@pytest.mark.parametrize('terminal', [False, True], ids=['repairs_before_next_fit', 'deadline_retains_evidence'])
def test_controller_delivers_actionable_cardinality_repair_or_truthful_terminal_abandonment(tmp_path, monkeypatch, terminal):
    clock = [100.]
    if terminal:
        monkeypatch.setattr(controller, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    model = CardinalityRepairModel(clock if terminal else None)
    result = asyncio.run(controller.run_one(StudyConfig(condition='periodic_reflection',
        allowance_seconds=60, trial_cap=8), tmp_path, tmp_path / 'run', model,
        trial_runner=trial, project={}))
    events = [json.loads(line) for line in (tmp_path / 'run/events.jsonl').read_text().splitlines()]
    contracts = [event for event in events if event['type'] == 'reflection_contract' and event['after_trial'] == 7]
    assert 'at most 6 items' in ' '.join(contracts[0]['errors'])
    assert len(contracts[0]['contract']['lesson_updates'][0]['evidence']) == 7
    if terminal:
        assert result['stop_reason'] == 'deadline' and result['trials'] == 7
        assert [event['valid'] for event in contracts] == [False]
        abandoned = [event for event in events if event['type'] == 'contract_abandoned']
        assert len(abandoned) == 1 and 'at most 6 items' in ' '.join(abandoned[0]['errors'])
        assert model.bad_calls == 1
        assert not any(lesson['id'] == 'learning_rate_progression' for lesson in result['lessons'])
    else:
        assert result['stop_reason'] == 'trial_cap' and result['trials'] == 8
        assert [event['valid'] for event in contracts] == [False, True]
        assert model.bad_calls == 2
        assert len(contracts[1]['contract']['lesson_updates'][0]['evidence']) == 6
        assert not any(event['type'] == 'contract_abandoned' for event in events)
