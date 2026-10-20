import asyncio
import copy
import json

import pytest

from study import reasoning
from study.controller import agent_result, run_one
from study.config import StudyConfig
from study.fake import FakeModel, scripted_contract
from study.problem import ProblemSpec
from study.tasks import get_adapter
from tests.test_problem import profile
from test_reasoning_controller import trial


@pytest.mark.parametrize('task', ['legacy', 'tabular_classification', 'tabular_regression'])
def test_all_features_is_explicit_and_numeric_aliases_are_rejected(task):
    from study.science import build_pipeline
    if task == 'legacy':
        build = build_pipeline
    else:
        value = profile(task, 'accuracy' if task.endswith('classification') else 'rmse')
        value['search_space']['models'] = ['random_forest']
        build = get_adapter(ProblemSpec.from_dict(value)).build_pipeline
    config = {'model': 'random_forest', 'preprocessing': 'none', 'params': {'max_features': 'all'}}
    assert build(config, seed=42).steps[-1][1].max_features == 1.0
    assert type(build(config, seed=42).steps[-1][1].max_features) is float
    for ambiguous in (1, 1.0, True):
        config['params']['max_features'] = ambiguous
        with pytest.raises(ValueError):
            build(config, seed=42)


@pytest.mark.parametrize('wrapper', [
    'Based on the completed trials, here is my assessment:\n```json\n%s\n```',
    'My assessment follows.\n%s\nThis concludes the assessment.',
    '```JSON\n%s\n```',
    'The comparison uses max_features="all".\n```json\n%s\n```\nThe word "all" identifies every feature.',
])
def test_single_wrapped_contract_retains_nested_values_and_quoted_braces(wrapper):
    value = {'summary': 'A literal {brace} is data.', 'evidence': [{'value': .9}], 'note': 'Quoted "text".'}
    assert reasoning.parse_contract(wrapper % json.dumps(value), allow_wrapper=True) == value


@pytest.mark.parametrize('content', [
    '{"a": 1} {"a": 2}', '```json\n{"a": 1}\n```\n```json\n{"a": 2}\n```',
    'Preamble {"a": NaN}', 'Preamble {"a": 1e309}', '[{"a": 1}]',
    '{"outer": {"a": 1}', '{"a": 1, "a": 2}',
    '{"a":1},"b":2', '```json\n{"a":1},"b":2\n```',
    '"a":1, {"b":2}', 'Review: {"a":1},"b":2',
    '```json\nPreamble {"a":1}\n```', '"a":1, ```json\n{"b":2}\n```',
    'Use "all". {"extra": 1}\n```json\n{"a": 1}\n```',
    'Use "all".\n```json\n{"a": 1}\n```\n"other": 2',
])
def test_wrapper_parser_rejects_ambiguous_malformed_and_nonfinite_objects(content):
    with pytest.raises(ValueError):
        reasoning.parse_contract(content, allow_wrapper=True)


def test_tool_arguments_do_not_accept_prose_wrappers():
    with pytest.raises(ValueError):
        reasoning.parse_contract('Use this: {"model":"logistic"}')


@pytest.mark.parametrize('claim', [
    'The best setting is optimal and represents the practical ceiling.',
    'Feature subsampling outperforms full feature access, confirming the plateau.',
    'Histogram gradient boosting performance is invariant to preprocessing choice.',
    'These results prove that capacity is not the limiting factor.',
    'Logistic regression underperforms, indicating strong nonlinear feature interactions.',
])
def test_overclaims_are_grounded_before_feedback_and_memory(claim):
    context = {'recent_trials': [{'trial_id': 6, 'status': 'completed', 'metrics': {'roc_auc': .9327}}], 'lessons': []}
    contract = scripted_contract('reflection', context)
    contract['summary'] = claim
    contract['lesson_updates'][0].update(summary=claim, status='supported')
    original = copy.deepcopy(contract)
    grounded, changes = reasoning.ground_contract(contract, context['recent_trials'])
    assert contract == original
    assert changes
    assert grounded['lesson_updates'][0]['interpretation']['summary'] == claim
    assert grounded['lesson_updates'][0]['interpretation']['status'] == 'unverified'
    assert claim not in grounded['lesson_updates'][0]['summary']
    assert '0.9327' in grounded['summary'] and '6' in grounded['summary']
    assert grounded['lesson_updates'][0]['status'] == 'inconclusive'
    ledger = reasoning.LessonMemory(6)
    ledger.update(original['lesson_updates'], context['recent_trials'])
    assert ledger.snapshot() == grounded['lesson_updates']


def test_scoped_observations_and_explicit_uncertainty_are_preserved():
    context = {'recent_trials': [{'trial_id': 1, 'status': 'completed', 'metrics': {'roc_auc': .9}}], 'lessons': []}
    contract = scripted_contract('reflection', context)
    contract['summary'] = 'Trial 1 recorded validation AUC 0.9 on this split.'
    contract['uncertainty'] = 'Whether a performance ceiling exists remains unknown.'
    grounded, changes = reasoning.ground_contract(contract, context['recent_trials'])
    assert grounded['summary'] == contract['summary']
    assert grounded['uncertainty'] == contract['uncertainty']


def test_effective_feature_count_reaches_agents_without_artifact_paths():
    result = {'artifact': '/private/model', 'actual_effective_config': {'params': {'max_features': 10}}, 'score': .9}
    visible = agent_result(result)
    assert visible['actual_effective_config']['params']['max_features'] == 10
    assert 'artifact' not in visible


def test_wrapped_overclaim_review_needs_no_extra_call_and_is_audited(tmp_path):
    class Reviewer(FakeModel):
        calls = 0
        contexts = []
        async def complete(self, messages, tools, *, timeout):
            self.calls += 1
            context = json.loads(messages[1]['content'])
            self.contexts.append(context)
            response = await super().complete(messages, tools, timeout=timeout)
            if messages[0]['content'].startswith('ROLE: supervisor'):
                contract = json.loads(response['message']['content'])
                contract['summary'] = 'The observed score proves that the configuration is optimal.'
                contract['lesson_updates'][0].update(summary=contract['summary'], status='supported')
                response['message']['content'] = 'Here is my review:\n```json\n' + json.dumps(contract) + '\n```'
            return response
    model = Reviewer()
    result = asyncio.run(run_one(StudyConfig(condition='frequent', trial_cap=2, lesson_memory=True),
        tmp_path, tmp_path / 'run', model, trial_runner=trial, project={}))
    assert result['stop_reason'] == 'trial_cap' and model.calls == 3
    assert 'optimal' not in model.contexts[-1]['lessons'][0]['summary']
    assert model.contexts[-1]['lessons'][0]['interpretation']['status'] == 'unverified'
    assert result['lessons'][0]['status'] == 'inconclusive'
    events = [json.loads(x) for x in (tmp_path / 'run/events.jsonl').read_text().splitlines()]
    assert any(e['type'] == 'contract_grounded' for e in events)
    assert all(e['valid'] for e in events if e['type'] == 'supervisor_contract')
    assert 'optimal' in json.dumps([e for e in events if e['type'] == 'model_call'])


def test_real_worker_all_features_fits_every_input_feature(tmp_path):
    import joblib
    from study.science import prepare_dataset, run_trial
    value = profile()
    value['search_space']['models'] = ['random_forest']
    problem = ProblemSpec.from_dict(value)
    prepare_dataset(tmp_path / 'data', problem=problem)
    result = asyncio.run(run_trial(tmp_path / 'data', tmp_path / 'fit',
        {'model': 'random_forest', 'preprocessing': 'none',
         'params': {'max_features': 'all', 'n_estimators': 10}}, seed=42, timeout=20, cores=2))
    assert result['status'] == 'completed', result
    estimator = joblib.load(result['artifact'])['pipeline'].steps[-1][1]
    assert all(tree.max_features_ == 6 for tree in estimator.estimators_)
    assert result['actual_effective_config']['params']['max_features'] == 6


def test_grounding_never_resurrects_superseded_lessons():
    lesson = {'id': 'old', 'status': 'superseded', 'summary': 'This proves an optimal setting.',
              'scope': 'This run only.',
              'evidence': [{'trial_id': 1, 'metric': 'roc_auc', 'split': 'validation', 'value': .9}]}
    result, changes = reasoning.ground_contract({'lesson_updates': [lesson]})
    assert result['lesson_updates'][0]['status'] == 'superseded'
    assert changes
