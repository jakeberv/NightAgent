"""Exercise missing observation notes at the real controller/model boundary."""
import asyncio
from copy import deepcopy
import json

import pytest

from study.config import StudyConfig
from study.controller import run_one
from study.recovery import recover_run
from test_reasoning import decision


class OmittingMemoryModel:
    """An external response fixture that writes a note only after a repair error."""
    def __init__(self, *, repair=True, empty_updates=False):
        self.repair = repair
        self.empty_updates = empty_updates
        self.calls = []

    async def complete(self, messages, tools, *, timeout):
        role = messages[0]['content'].splitlines()[0].removeprefix('ROLE: ')
        context = json.loads(messages[1]['content'])
        self.calls.append({'role': role, 'context': context, 'tools': deepcopy(tools)})
        completed = next((row for row in reversed(context['recent_trials'])
                          if row['status'] == 'completed' and row.get('metrics', {}).get('roc_auc') is not None), None)
        evidence = [{'trial_id': completed['trial_id'], 'metric': 'roc_auc'}] if completed else []
        contract = {'summary': 'The run is collecting validation observations.', 'evidence': evidence}
        if role == 'researcher':
            contract = {**decision(), 'baseline_trial_id': completed['trial_id'] if completed else None,
                        'evidence': evidence}
            if context['last_supervisor_feedback'] is not None:
                contract.update(supervisor_response='modified', response_reason='Compare another permitted configuration.')
            if self.empty_updates and 'lessons' in context:
                contract['lesson_updates'] = []
            if self.repair and evidence and any(
                    message['role'] == 'tool' and 'lesson_updates' in message.get('content', '')
                    for message in messages):
                contract['lesson_updates'] = [{'id': 'first_observation', 'status': 'inconclusive',
                    'summary': 'The first trial provides a validation observation.',
                    'scope': 'This observation applies to this run and validation split.', 'evidence': evidence}]
            message = {'role': 'assistant', 'tool_calls': [{'id': str(len(self.calls)), 'type': 'function',
                'function': {'name': 'run_analysis', 'arguments': json.dumps({'model': 'logistic',
                    'preprocessing': 'standard', 'params': {'C': context['trials_attempted'] + 1},
                    'intent': contract})}}]}
        else:
            if role == 'supervisor':
                contract.update(assessment='Recorded trials provide observations for comparison.',
                    unresolved_question='Would another configuration improve validation performance?',
                    recommendation={'model': 'logistic', 'preprocessing': 'standard',
                                    'params': {'C': context['trials_attempted'] + 1}},
                    expected_outcome='The next trial will add a validation observation.')
                contract['motivation'] = 'Use the remaining budget to compare model configurations.'
                if context['supervisor_stage'] == 'framing':
                    contract['hypothesis'] = 'Another configuration may improve validation performance.'
                else:
                    contract.update(alternative_explanations=[
                        'Model capacity may affect validation performance.',
                        'The fixed validation sample may affect the observed difference.'],
                        cross_field_connection='A capacity comparison may help test the prediction.',
                        falsifying_outcome='An unchanged score would weaken the prediction on this split.',
                        resource_check='Use one fit within the remaining trial and time allowance.')
            else:
                contract.update(what_changed='The latest trial added a validation observation.',
                    uncertainty='One split does not establish broader generalization.',
                    next_comparison={'model': 'logistic', 'preprocessing': 'standard',
                                     'params': {'C': context['trials_attempted'] + 1}})
            message = {'role': 'assistant', 'content': json.dumps(contract)}
        return {'message': message, 'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'cost': .01}}


def read_events(run_dir):
    return [json.loads(line) for line in (run_dir / 'events.jsonl').read_text().splitlines()]


@pytest.mark.parametrize('condition', ['researcher_alone', 'frequent', 'periodic', 'periodic_reflection'])
@pytest.mark.parametrize('empty_updates', [False, True], ids=['omitted', 'empty'])
def test_empty_memory_requires_cited_note_and_repairs_before_next_fit(tmp_path, condition, empty_updates):
    # Removing the contextual note requirement would fit immediately on the omitted response.
    model = OmittingMemoryModel(empty_updates=empty_updates)
    fit_call_counts = []

    async def fit(data_dir, trial_dir, config, *, seed, timeout):
        fit_call_counts.append(len(model.calls))
        return {'status': 'completed', 'metrics': {'roc_auc': .9}, 'validation_auc': .9,
                'artifact': 'fixture', 'artifact_hash': 'fixture-hash'}

    run_dir = tmp_path / 'run'
    summary = asyncio.run(run_one(StudyConfig(condition=condition, trial_cap=3), tmp_path,
        run_dir, model, trial_runner=fit, project={}))
    researcher_calls = [call for call in model.calls if call['role'] == 'researcher']
    assert [call['context']['trials_attempted'] for call in researcher_calls] == [0, 1, 1, 2]
    assert summary['trials'] == 3 and summary['stop_reason'] == 'trial_cap'
    events = read_events(run_dir)
    decisions = [event for event in events if event['type'] == 'decision_contract']
    assert [event['valid'] for event in decisions] == [True, False, True, True]
    assert 'lesson_updates' in ' '.join(decisions[1]['errors'])
    accepted = decisions[2]
    assert events.index(accepted) < next(index for index, event in enumerate(events)
        if event['type'] == 'trial_started' and event['trial_id'] == 2)
    assert fit_call_counts[1] == model.calls.index(researcher_calls[2]) + 1
    assert summary['accounting']['calls'] == len(model.calls)
    assert summary['accounting']['known_cost'] == pytest.approx(len(model.calls) * .01)
    assert summary['accounting']['cost_complete']
    lesson = summary['lessons'][0]
    assert lesson['status'] == 'inconclusive'
    assert lesson['evidence'] == [{'trial_id': 1, 'metric': 'roc_auc', 'split': 'validation', 'value': .9}]
    assert lesson['summary'] != 'The first trial provides a validation observation.'
    assert lesson['interpretation']['status'] == 'unverified'
    assert researcher_calls[-1]['context']['lessons'] == [
        {key: value for key, value in lesson.items() if key != 'interpretation'}]
    assert json.loads((run_dir / 'lessons.json').read_text())['lessons'] == summary['lessons']
    assert recover_run(run_dir)['lessons'] == summary['lessons']
    # The request schema describes the same contextual obligation enforced before fitting.
    schemas = [call['tools'][0]['function']['parameters']['properties']['intent']
               for call in researcher_calls]
    assert ['lesson_updates' in schema['required'] for schema in schemas] == [False, True, True, False]
    assert schemas[1]['properties']['lesson_updates']['minItems'] == 1
    assert not decisions[-1]['contract'].get('lesson_updates')


def test_repeated_note_omission_stops_at_existing_turn_bound_without_another_fit(tmp_path):
    model = OmittingMemoryModel(repair=False)
    fits = []

    async def fit(*args, **kwargs):
        fits.append(True)
        return {'status': 'completed', 'metrics': {'roc_auc': .9}, 'validation_auc': .9,
                'artifact': 'fixture', 'artifact_hash': 'fixture-hash'}

    summary = asyncio.run(run_one(StudyConfig(trial_cap=3, max_turns_without_trial=2),
        tmp_path, tmp_path / 'run', model, trial_runner=fit, project={}))
    assert summary['stop_reason'] == 'no_progress' and summary['trials'] == 1
    assert len(fits) == 1 and summary['accounting']['calls'] == 3
    assert summary['accounting']['known_cost'] == pytest.approx(.03)
    assert summary['lessons'] == [] and not (tmp_path / 'run/lessons.json').exists()
    assert [event['valid'] for event in read_events(tmp_path / 'run')
            if event['type'] == 'decision_contract'] == [True, False, False]


def test_equivalent_proposal_does_not_seed_memory_before_admitted_fit(tmp_path):
    class EquivalentNoteModel(OmittingMemoryModel):
        second_trial_attempts = 0

        async def complete(self, messages, tools, *, timeout):
            response = await super().complete(messages, tools, timeout=timeout)
            if self.calls[-1]['context']['trials_attempted'] == 1:
                self.second_trial_attempts += 1
                function = response['message']['tool_calls'][0]['function']
                arguments = json.loads(function['arguments'])
                if self.second_trial_attempts == 2:
                    arguments['params']['C'] = 1  # A repaired note accompanies a reused configuration.
                elif self.second_trial_attempts == 3:
                    arguments['intent'].pop('lesson_updates')
                function['arguments'] = json.dumps(arguments)
            return response

    async def fit(*args, **kwargs):
        return {'status': 'completed', 'metrics': {'roc_auc': .9}, 'validation_auc': .9,
                'artifact': 'fixture', 'artifact_hash': 'fixture-hash'}

    model = EquivalentNoteModel()
    summary = asyncio.run(run_one(StudyConfig(trial_cap=3), tmp_path, tmp_path / 'run',
        model, trial_runner=fit, project={}))
    assert summary['trials'] == 3 and summary['stop_reason'] == 'trial_cap'
    assert [call['context']['trials_attempted'] for call in model.calls] == [0, 1, 1, 1, 1, 2]
    assert all(call['context']['lessons'] == [] for call in model.calls[:-1])
    assert model.calls[-1]['context']['lessons'][0]['id'] == 'first_observation'
    events = read_events(tmp_path / 'run')
    decisions = [event for event in events if event['type'] == 'decision_contract']
    assert [event['valid'] for event in decisions] == [True, False, True, False, True, True]
    assert decisions[2]['executed'] is False and decisions[2]['not_executed_reason'] == 'equivalent'
    assert events.index(decisions[4]) < next(index for index, event in enumerate(events)
        if event['type'] == 'lesson_memory')
    assert summary['accounting']['calls'] == 6


@pytest.mark.parametrize('status,metrics', [
    ('failed', {'roc_auc': .9}), ('completed', {}),
    ('completed', {'non_numeric': 'unknown', 'boolean': True}),
])
def test_failed_or_uncitable_trials_do_not_require_observation_notes(tmp_path, status, metrics):
    model = OmittingMemoryModel(repair=False)

    async def fit(*args, **kwargs):
        return {'status': status, 'metrics': metrics, 'artifact': 'fixture', 'artifact_hash': 'fixture-hash'}

    summary = asyncio.run(run_one(StudyConfig(trial_cap=2), tmp_path, tmp_path / 'run',
        model, trial_runner=fit, project={}))
    assert summary['trials'] == 2 and summary['accounting']['calls'] == 2
    assert summary['lessons'] == []
    assert all(event['valid'] for event in read_events(tmp_path / 'run')
               if event['type'] == 'decision_contract')


def test_omission_control_and_new_run_keep_memory_isolated(tmp_path):
    async def fit(*args, **kwargs):
        return {'status': 'completed', 'metrics': {'roc_auc': .9}, 'validation_auc': .9,
                'artifact': 'fixture', 'artifact_hash': 'fixture-hash'}

    control = OmittingMemoryModel(repair=False)
    result = asyncio.run(run_one(StudyConfig(condition='periodic_reflection', lesson_memory=False, trial_cap=3),
        tmp_path, tmp_path / 'off', control, trial_runner=fit, project={}))
    assert result['trials'] == 3 and result['stop_reason'] == 'trial_cap'
    assert 'lessons' not in result and not (tmp_path / 'off/lessons.json').exists()
    assert all('lessons' not in call['context'] for call in control.calls)
    assert not any(event['type'] == 'lesson_memory' for event in read_events(tmp_path / 'off'))
    for call in control.calls:
        if call['role'] == 'researcher':
            schema = call['tools'][0]['function']['parameters']['properties']['intent']
            assert 'lesson_updates' not in schema['properties']
    first = OmittingMemoryModel()
    result = asyncio.run(run_one(StudyConfig(trial_cap=3), tmp_path, tmp_path / 'on',
        first, trial_runner=fit, project={}))
    assert result['lessons']
    fresh = OmittingMemoryModel(repair=False)
    result = asyncio.run(run_one(StudyConfig(trial_cap=1), tmp_path, tmp_path / 'fresh',
        fresh, trial_runner=fit, project={}))
    assert result['trials'] == 1 and result['accounting']['calls'] == 1
    assert result['lessons'] == [] and fresh.calls[0]['context']['lessons'] == []
