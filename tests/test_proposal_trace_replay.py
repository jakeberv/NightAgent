"""Replay the live proposal failures without journal files, training, or API calls."""
import asyncio
from copy import deepcopy
import json
import hashlib

import numpy as np
from pathlib import Path

import pytest

from study.config import StudyConfig
from study.controller import run_one
from study.fake import scripted_contract
from study.problem import load_problem, prepared_data_fingerprint


FAILURES = json.loads((Path(__file__).parent / 'fixtures/proposal-failures.json').read_text())['cases']
PROBLEM = load_problem(Path(__file__).resolve().parents[1] / 'study/problems/fashion-mnist.yaml')


def experiment(index):
    # Trial 5 reproduces the old MLP recommendation that fell outside recent history.
    if index == 5:
        return deepcopy(FAILURES['completed_candidate']['candidate'])
    return {'model': 'torch_cnn', 'preprocessing': 'none',
            'params': {'epochs': 5, 'batch_size': 128, 'channels': 16,
                       'learning_rate': .0001 * index, 'weight_decay': .001}}


async def measured_trial(data_dir, trial_dir, config, *, seed, timeout):
    assert 'intent' not in config
    assert seed == 42
    return {'status': 'completed', 'score': .8, 'metrics': {'accuracy': .8},
            'artifact': 'trace-replay-fixture', 'artifact_hash': str(trial_dir)}


class TraceModel:
    """Script model output only; the production controller owns all validation."""
    def __init__(self, role=None, failure=None):
        self.role, self.failure = role, failure
        self.injected = False
        self.contexts = []

    async def complete(self, messages, tools, *, timeout):
        role = messages[0]['content'].splitlines()[0].removeprefix('ROLE: ')
        context = json.loads(messages[1]['content'])
        self.contexts.append((role, deepcopy(context)))
        count = context['trials_attempted']
        contract = scripted_contract(role, context)
        # The new request contract retains hypotheses and evidence but has no
        # independently authored claim about the executable parameter change.
        contract.pop('change', None)
        if role == 'researcher':
            contract['baseline_trial_id'] = count or None
            candidate = experiment(count + 1)
            candidate['intent'] = contract
            message = {'role': 'assistant', 'tool_calls': [{'id': str(len(self.contexts)),
                'type': 'function', 'function': {'name': 'run_analysis',
                'arguments': json.dumps(candidate)}}]}
        else:
            field = 'recommendation' if role == 'supervisor' else 'next_comparison'
            candidate = experiment(count + 1)
            trigger = 18 if self.failure == 'completed_candidate' else 1
            if role == self.role and count == trigger and not self.injected:
                candidate = deepcopy(FAILURES[self.failure]['candidate'])
                self.injected = True
            contract[field] = candidate
            message = {'role': 'assistant', 'content': json.dumps(contract)}
        return {'message': message, 'usage': {'prompt_tokens': 2, 'completion_tokens': 2, 'cost': 0}}


def replay(tmp_path, model, *, condition='frequent', trials=7):
    # A tiny prepared fixture preserves normal profile/identity validation.
    # The injected trial runner does not train or read the real Fashion data.
    partitions = {}
    for split in ('train', 'validation', 'test'):
        path = tmp_path / f'{split}.npz'
        np.savez(path, X=np.zeros((2, 784)), y=np.array([0, 1]))
        partitions[split] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {'dataset': PROBLEM.id, 'problem': PROBLEM.to_dict(),
        'problem_hash': PROBLEM.fingerprint, 'source_sha256': 'trace-fixture',
        'seed': 42, 'split_protocol': PROBLEM.to_dict()['evaluation']['split'],
        'feature_names': [f'pixel_{i}' for i in range(784)], 'partitions': partitions}
    manifest['data_fingerprint'] = prepared_data_fingerprint(manifest)
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    run_dir = tmp_path / 'run'
    result = asyncio.run(run_one(StudyConfig(condition=condition, device='cpu',
        lesson_memory=False, trial_cap=trials), tmp_path, run_dir, model,
        trial_runner=measured_trial, project={'n_features': 784}, problem=PROBLEM))
    events = [json.loads(line) for line in (run_dir / 'events.jsonl').read_text().splitlines()]
    return result, events


@pytest.mark.parametrize('role', ['supervisor', 'reflection'])
@pytest.mark.parametrize('failure', ['out_of_bounds', 'unsupported_seed', 'completed_candidate'])
def test_real_advisor_failures_are_repaired_before_becoming_active(tmp_path, role, failure):
    model = TraceModel(role, failure)
    condition = 'frequent' if role == 'supervisor' else 'periodic_reflection'
    trials = 20 if failure == 'completed_candidate' else 7
    result, events = replay(tmp_path, model, condition=condition, trials=trials)
    assert model.injected, 'The replay must reach its source failure.'
    assert result['stop_reason'] == 'trial_cap' and result['trials'] == trials
    target = 18 if failure == 'completed_candidate' else 1
    contracts = [e for e in events if e['type'] == f'{role}_contract' and e['after_trial'] == target]
    assert [e['valid'] for e in contracts] == [False, True]
    assert contracts[0]['errors']
    if failure == 'completed_candidate':
        context = next(context for observed_role, context in model.contexts
                       if observed_role == role and context['trials_attempted'] == target)
        assert 5 not in [row['trial_id'] for row in context['recent_trials']]
    field = 'recommendation' if role == 'supervisor' else 'next_comparison'
    assert contracts[-1]['contract'][field] == experiment(target + 1)
    assert not any(e['type'] == 'experiment_reused' for e in events)


def test_fresh_executable_advice_and_change_free_intents_complete_without_repair(tmp_path):
    model = TraceModel()
    result, events = replay(tmp_path, model)
    assert result['stop_reason'] == 'trial_cap' and result['trials'] == 7
    assert all(e['valid'] for e in events if e['type'].endswith('_contract'))
    assert not any(e['type'] == 'experiment_reused' for e in events)
    started = [e for e in events if e['type'] == 'model_call_started' and e['role'] == 'researcher']
    assert len(started) == 7
    decisions = [e['contract'] for e in events if e['type'] == 'decision_contract']
    assert all(isinstance(contract['change'], str) and contract['change'] for contract in decisions)
    assert all(context['training_seed'] == 42 for _, context in model.contexts)


def test_fulfilled_periodic_advice_is_annotated_from_completed_registry(tmp_path):
    model = TraceModel()
    result, _ = replay(tmp_path, model, condition='periodic', trials=6)
    assert result['stop_reason'] == 'trial_cap'
    context = next(context for role, context in model.contexts
                   if role == 'researcher' and context['trials_attempted'] == 4)
    assert context['last_supervisor_feedback']['recommendation'] == experiment(4)
    assert context['recommendation_completed_trial_ids'] == [4]


def test_source_narrative_payload_mismatch_is_removed_from_request_contract():
    from study.reasoning import request_contract_schema, schema_errors
    source = FAILURES['narrative_payload_mismatch']
    history = {'trial_id': 4, 'status': 'completed', 'metrics': {'accuracy': .8}}
    context = {'objective': {'metric': 'accuracy'}, 'recent_trials': [history]}
    contract = scripted_contract('researcher', context)
    contract.pop('change', None)
    schema = request_contract_schema('researcher')
    assert not schema_errors(contract, schema, 'decision request')
    # The source claimed to modify the CNN while submitting the same parameters.
    # That competing action description is no longer accepted from the model.
    contract['change'] = source['observed_change']
    assert schema_errors(contract, schema, 'decision request')


def test_offline_candidate_respects_narrow_numeric_enum_and_skips_completed_values():
    from study.fake import scripted_candidate
    from study.tasks import get_adapter
    schema = deepcopy(get_adapter(PROBLEM).analysis_schema)
    parameter_schema = schema['allOf'][0]['then']['properties']['params']['properties']
    parameter_schema['C'] = {'type': 'number', 'minimum': .1, 'maximum': .2, 'enum': [.1, .2]}
    context = {'permitted_experiments': schema, 'completed_configurations': {
        'parameter_bases': {'logistic': {}}, 'entries': [
            {'model': 'logistic', 'preprocessing': 'standard', 'params': {'C': .1}}]}}
    assert scripted_candidate(context)['params']['C'] == .2
    context['completed_configurations']['entries'].append(
        {'model': 'logistic', 'preprocessing': 'standard', 'params': {'C': .2}})
    with pytest.raises(ValueError, match='exhausted'):
        scripted_candidate(context)


def test_offline_candidate_handles_schema_without_numeric_knobs_and_known_exhaustion():
    from study.fake import scripted_candidate
    from study.tasks import get_adapter
    schema = deepcopy(get_adapter(PROBLEM).analysis_schema)
    schema['allOf'][0]['then']['properties']['params']['properties'] = {}
    context = {'permitted_experiments': schema}
    candidate = scripted_candidate(context)
    assert candidate == {'model': 'logistic', 'preprocessing': 'standard', 'params': {}}
    context['completed_configurations'] = {'parameter_bases': {'logistic': {}},
        'entries': [{'model': 'logistic', 'preprocessing': 'standard', 'params': {}}]}
    with pytest.raises(ValueError, match='exhausted'):
        scripted_candidate(context)
