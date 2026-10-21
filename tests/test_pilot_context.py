"""Regressions from the October 20 Fashion pilot, without model/API calls."""
import copy
import json

import pytest


def test_target_status_reports_crossing_and_direction_without_inventing_measurements():
    from study.run_context import target_status
    targets = [{'name': 'stretch', 'value': .85}]
    result = target_status(targets, {'metric': 'accuracy', 'direction': 'maximize'},
                           {'score': .8743}, {'stretch': {'trial_id': 4, 'elapsed_seconds': 95}})
    assert result[0]['reached'] is True and result[0]['remaining_gap'] == 0
    assert result[0]['first_trial_id'] == 4
    assert 'reached' in result[0]['sentence'] and '0.85' in result[0]['sentence']
    result = target_status([{'name': 'loss', 'value': .2}],
                          {'metric': 'loss', 'direction': 'minimize'}, {'score': .3}, {})
    assert result[0]['reached'] is False
    assert result[0]['remaining_gap'] == pytest.approx(.1)
    unknown = target_status(targets, {'metric': 'accuracy', 'direction': 'maximize'}, None, {})
    assert unknown[0]['remaining_gap'] is None and not unknown[0]['reached']


def test_capacity_includes_pending_review_reflection_and_future_calls():
    from study.run_context import capacity_estimate
    from study.config import StudyConfig
    config = StudyConfig(condition='periodic_reflection', trial_cap=12)
    # Starting a review after trial 3: 10s review + 10s reflection, then
    # three fits at 15s each and two intervening reflections at 10s each = 85s.
    result = capacity_estimate(config, attempted=3, remaining=85,
        history=[{'duration_seconds': 5}], call_durations={
            'researcher': [10], 'supervisor': [10], 'reflection': [10]}, role='supervisor')
    assert result['estimated_additional_trials'] == 3
    assert result['estimated_seconds'] == 85
    assert 'estimate' in result['sentence'].lower()
    result = capacity_estimate(config, attempted=11, remaining=100,
        history=[{'duration_seconds': 5}], call_durations={'researcher': [10]}, role='researcher')
    assert result['estimated_additional_trials'] == 1
    assert result['estimated_seconds'] == 15
    result = capacity_estimate(config, attempted=0, remaining=300,
        history=[], call_durations={}, role='supervisor', framing=True)
    assert result['estimated_additional_trials'] is None


def test_context_retains_measurements_errors_and_actual_device_without_duplicate_configs():
    from study.run_context import compact_result
    row = {'trial_id': 7, 'status': 'completed', 'config': {'model': 'torch_cnn', 'params': {'epochs': 5}},
        'metrics': {'accuracy': .8743}, 'score': .8743, 'duration_seconds': 5,
        'effective_config': {'params': {'device': 'cpu'}},
        'actual_effective_config': {'params': {'device': 'mps', 'epochs': 5}},
        'fit_diagnostics': {'device': 'mps', 'inference_device': 'cpu', 'actual_epochs': 5,
                            'training_loss': [.8, .7, .6, .5, .4]},
        'artifact': 'long/path', 'artifact_hash': 'hash', 'provenance': {'x': 'y'}}
    original = copy.deepcopy(row)
    compact = compact_result(row)
    assert compact['metrics'] == row['metrics'] and compact['config'] == row['config']
    assert compact['fit_diagnostics']['device'] == 'mps'
    assert 'effective_config' not in compact and 'actual_effective_config' not in compact
    assert 'training_loss' not in compact['fit_diagnostics']
    assert compact['fit_diagnostics']['final_training_loss'] == .4
    assert compact_result({'status': 'failed', 'error': 'fit failed'})['error'] == 'fit failed'
    assert row == original
    assert len(json.dumps(compact)) < len(json.dumps(row)) * .75


def test_constructor_diagnostics_do_not_claim_cpu_execution_for_neural_models():
    from study.diagnostics import describe_experiment
    from study.problem import load_problem
    problem = load_problem('study/problems/fashion-mnist.yaml')
    d = describe_experiment({'model': 'torch_cnn', 'preprocessing': 'none', 'params': {}},
                           problem=problem, project={'n_features': 784}, seed=42)
    assert 'device' not in d['effective_config']['params']


def test_factual_assessment_exposes_confounding_and_preserves_conditional_prediction():
    from study.reasoning import ground_contract
    history = [
        {'trial_id': 7, 'status': 'completed', 'config': {'model': 'torch_cnn', 'params': {'learning_rate': .009}}, 'metrics': {'accuracy': .8743}},
        {'trial_id': 9, 'status': 'completed', 'config': {'model': 'torch_mlp', 'params': {'learning_rate': .005}}, 'metrics': {'accuracy': .8413}}]
    c = {'summary': 'The architecture comparison isolated spatial structure.',
         'assessment': 'This comparison isolated architecture as the primary difference.',
         'expected_outcome': 'Accuracy may increase, or decrease if lighter regularization causes overfitting.',
         'evidence': [{'trial_id': t, 'metric': 'accuracy', 'split': 'validation', 'value': v}
                      for t, v in [(7, .8743), (9, .8413)]]}
    result, changes = ground_contract(c, history)
    assert result['expected_outcome'] == c['expected_outcome']
    assert 'isolated architecture' not in result['assessment']
    assert 'confounded' in result['comparison_scope']
    assert result['interpretation_status'] == 'unverified'
    assert '0.8743' in result['summary'] and '0.8413' in result['summary']
    assert any(x['field'] == 'assessment' and x['original'] == c['assessment'] for x in changes)


def test_stale_target_sentence_replaced_but_action_retained_and_resource_math_owned_by_runner():
    from study.reasoning import ground_contract
    c = {'summary': 'A new experiment is planned.', 'assessment': 'Some trials completed.',
         'recommendation': 'Test batch size 128. We still need to reach the 0.85 stretch target.',
         'resource_check': 'We can run 30 more trials.', 'evidence': []}
    target = {'name': 'stretch', 'threshold': .85, 'reached': True,
              'sentence': 'The stretch target (0.85) has been reached.'}
    result, changes = ground_contract(c, [], targets=[target],
        capacity={'sentence': 'The time estimate allows 3 additional trials including API calls.'})
    assert result['recommendation'].startswith('Test batch size 128.')
    assert 'still need' not in result['recommendation'] and 'has been reached' in result['recommendation']
    assert result['resource_check'].startswith('The time estimate allows 3')
    assert any(x['field'] == 'recommendation' for x in changes)


def test_post_review_estimate_does_not_charge_completed_api_call_twice():
    from study.run_context import capacity_estimate
    from study.config import StudyConfig
    result = capacity_estimate(StudyConfig(condition='periodic_reflection', trial_cap=4),
        attempted=3, remaining=25, history=[{'duration_seconds': 5}],
        call_durations={'researcher': [10], 'reflection': [10], 'supervisor': [15]},
        role='supervisor', phase_completed=True)
    assert result['estimated_additional_trials'] == 1 and result['estimated_seconds'] == 25


def test_target_named_loss_does_not_rewrite_training_loss_observation():
    from study.reasoning import ground_contract
    c = {'hypothesis': 'The training loss may decrease with more epochs.'}
    result, _ = ground_contract(c, [], targets=[{
        'name': 'loss', 'threshold': .2, 'sentence': 'The loss target (0.2) has not been reached.'}])
    assert result['hypothesis'] == c['hypothesis']


def test_compacted_feedback_keeps_advice_and_raw_lessons_stay_intact():
    from study.run_context import compact_feedback, compact_lessons
    lesson = {'id': 'a', 'evidence': [{'trial_id': 1}], 'interpretation': {'summary': 'Raw claim.'},
              'summary': 'Trial 1 scored 0.8.', 'scope': 'This split.', 'status': 'supported'}
    c = {'recommendation': 'Compare the next configuration.', 'lesson_updates': [lesson],
         'hypothesis': 'Capacity may matter.'}
    original = copy.deepcopy(c)
    assert compact_feedback(c) == {'recommendation': c['recommendation'], 'hypothesis': c['hypothesis']}
    assert compact_lessons([lesson])[0]['evidence'] == lesson['evidence']
    assert 'interpretation' not in compact_lessons([lesson])[0]
    assert c == original


def test_refreshed_context_supplies_target_state_and_preserves_raw_trial_details(tmp_path):
    import asyncio
    from study.config import StudyConfig
    from study.controller import run_one
    from test_reasoning_controller import StructuredModel
    async def fit(*args, **kwargs):
        return {'status': 'completed', 'score': .96, 'metrics': {'roc_auc': .96},
                'artifact': 'fake', 'artifact_hash': 'hash',
                'actual_effective_config': {'params': {'max_features': 10}}}
    model = StructuredModel(memory=True)
    result = asyncio.run(run_one(StudyConfig(trial_cap=2), tmp_path, tmp_path/'run', model,
                                trial_runner=fit, project={}))
    assert result['stop_reason'] == 'trial_cap'
    before, after = model.contexts
    assert not any(t['reached'] for t in before['target_status'])
    assert all(t['reached'] and t['remaining_gap'] == 0 for t in after['target_status'])
    assert after['capacity_estimate']['estimated_additional_trials'] == 1
    assert 'actual_effective_config' not in after['recent_trials'][0]
    events = [json.loads(line) for line in (tmp_path/'run/events.jsonl').read_text().splitlines()]
    assert next(e for e in events if e['type']=='trial_finished')['result']['actual_effective_config']['params']['max_features'] == 10


def test_target_repair_preserves_experiment_when_action_and_target_share_sentence():
    from study.reasoning import ground_contract
    c = {'next_comparison': 'Test torch_cnn with batch_size=128 to approach the 0.85 stretch target.'}
    result, _ = ground_contract(c, [], targets=[{
        'name': 'stretch', 'threshold': .85, 'sentence': 'The stretch target (0.85) has been reached.'}])
    assert 'Test torch_cnn with batch_size=128.' in result['next_comparison']
    assert 'has been reached' in result['next_comparison']
    assert 'approach' not in result['next_comparison']


def test_partial_configs_retain_scientific_defaults_and_actual_device():
    from study.run_context import compact_result
    result = compact_result({'config': {'model': 'torch_cnn', 'params': {}},
        'seed': 42, 'allocated_cores': 4,
        'actual_effective_config': {'params': {'architecture': 'cnn', 'device': 'mps',
            'random_state': 42, 'batch_size': 128, 'channels': 16, 'epochs': 3,
            'learning_rate': .001, 'weight_decay': 0.}},
        'fit_diagnostics': {'device': 'mps', 'actual_epochs': 3}})
    assert result['resolved_parameters'] == {'batch_size': 128, 'channels': 16, 'epochs': 3,
                                            'learning_rate': .001, 'weight_decay': 0.}
    assert result['fit_diagnostics']['device'] == 'mps'


def test_grounding_preserves_distinct_unverified_alternatives_and_valid_schema():
    from test_supervisor import review
    from study.reasoning import ground_contract, validate_contract
    c = review()
    c['alternative_explanations'] = ['The stretch target may need a wider model.',
                                     'The stretch target may need a lower learning rate.']
    assert not validate_contract(c, 'supervisor', [])
    result, _ = ground_contract(c, [], targets=[{
        'name': 'stretch', 'threshold': .85, 'sentence': 'The stretch target (0.85) has been reached.'}])
    assert not validate_contract(result, 'supervisor', [])
    assert result['alternative_explanations'] == c['alternative_explanations']
    assert result['interpretation_status'] == 'unverified'


def test_reflection_keeps_permitted_menu_after_project_schema_compaction(tmp_path):
    import asyncio
    from study.config import StudyConfig
    from study.controller import run_one
    from test_supervisor import ObservedModel
    from test_reasoning_controller import trial
    model = ObservedModel()
    result = asyncio.run(run_one(StudyConfig(condition='periodic_reflection', trial_cap=2),
        tmp_path, tmp_path/'run', model, trial_runner=trial, project={}))
    assert result['stop_reason'] == 'trial_cap'
    reflection = next(context for role, context, _ in model.observed if role=='reflection')
    assert 'model' in reflection['permitted_experiments']['properties']
    assert 'analysis_schema' not in reflection['project']


def test_runner_grounding_failure_stops_without_paid_model_repair(tmp_path, monkeypatch):
    import asyncio
    from study.config import StudyConfig
    from study.controller import run_one
    from test_reasoning_controller import StructuredModel, trial
    def broken_grounder(contract, history, **kwargs):
        return {**contract, 'summary': 'Not a complete sentence'}, []
    monkeypatch.setattr('study.reasoning.ground_contract', broken_grounder)
    model = StructuredModel()
    result = asyncio.run(run_one(StudyConfig(trial_cap=2), tmp_path, tmp_path/'run', model,
                                trial_runner=trial, project={}))
    assert result['stop_reason'] == 'invalid_grounded_contract'
    assert model.calls == 1 and result['trials'] == 0


@pytest.mark.parametrize('field', ['hypothesis', 'expected_outcome', 'falsifying_outcome', 'uncertainty'])
def test_target_mentions_do_not_destroy_explicitly_unverified_predictions(field):
    from study.reasoning import ground_contract
    c = {field: 'Accuracy may exceed the stretch target, or decrease if lighter regularization causes overfitting.'}
    result, _ = ground_contract(c, [], targets=[{
        'name': 'stretch', 'threshold': .85, 'sentence': 'The stretch target (0.85) has been reached.'}])
    assert result[field] == c[field]


@pytest.mark.parametrize('field', ['change', 'recommendation', 'next_comparison'])
def test_target_repair_preserves_actions_beyond_test_verb(field):
    from study.reasoning import ground_contract
    result, _ = ground_contract({field: 'Increase batch_size to 256 to approach the stretch target.'}, [], targets=[{
        'name': 'stretch', 'threshold': .85, 'sentence': 'The stretch target (0.85) has been reached.'}])
    assert 'Increase batch_size to 256.' in result[field]
    assert 'has been reached' in result[field]


def test_target_repair_does_not_mistake_past_experiment_for_target_attainment():
    from study.reasoning import ground_contract
    c = {'next_comparison': 'Compare CNN with the MLP that has been tested to approach the stretch target.'}
    result, _ = ground_contract(c, [], targets=[{
        'name': 'stretch', 'threshold': .85, 'sentence': 'The stretch target (0.85) has been reached.'}])
    assert 'Compare CNN with the MLP that has been tested.' in result['next_comparison']


@pytest.mark.parametrize('field', ['recommendation', 'next_comparison', 'change'])
@pytest.mark.parametrize('sentence,action', [
    ('Compare batch sizes 64 and 128 because the stretch target has been reached.', 'Compare batch sizes 64 and 128.'),
    ('The stretch target has not been reached, so increase batch_size to 256.', 'Increase batch_size to 256.'),
    ('The stretch target has been reached; compare batch sizes 64 and 128.', 'Compare batch sizes 64 and 128.')])
def test_target_status_clause_repair_preserves_actions_on_either_side(field, sentence, action):
    from study.reasoning import ground_contract
    result, _ = ground_contract({field: sentence}, [], targets=[{
        'name': 'stretch', 'threshold': .85, 'sentence': 'The stretch target (0.85) has been reached.'}])
    assert action in result[field]
    assert 'The stretch target (0.85) has been reached.' in result[field]
    assert 'has not been reached' not in result[field]


@pytest.mark.parametrize('status', ['failed', 'timeout'])
def test_unfitted_trial_context_keeps_known_constructor_science(status):
    from study.run_context import compact_result
    compact = compact_result({'status': status, 'config': {'model': 'torch_cnn', 'params': {}},
        'effective_config': {'params': {'batch_size': 128, 'channels': 16,
            'learning_rate': .001, 'random_state': 42, 'n_jobs': 4, 'device': 'cpu'}}})
    assert compact['resolved_parameters'] == {'batch_size': 128, 'channels': 16, 'learning_rate': .001}


@pytest.mark.parametrize('requested,effective,changed', [
    ([{'epochs': 3}, {'epochs': 5, 'learning_rate': .001}],
     [{'epochs': 3, 'learning_rate': .001}, {'epochs': 5, 'learning_rate': .001}], 'epochs'),
    ([{}, {'C': 1.0}], [{'C': 1.0}, {'C': 1.0}], None),
    ([{'max_features': .5}, {'max_features': 10}], [{'max_features': 10}, {'max_features': 10}], None)])
def test_comparison_scope_uses_resolved_science_instead_of_request_spelling(requested, effective, changed):
    from study.reasoning import observed_scope
    history = [{'trial_id': i+1, 'status': 'completed',
                'config': {'model': 'same-model', 'params': requested[i]},
                'actual_effective_config': {'model': 'same-model', 'params': {
                    **effective[i], 'device': ('cpu', 'mps')[i], 'n_jobs': i+1, 'random_state': i}}}
               for i in range(2)]
    scope = observed_scope([{'trial_id': 1}, {'trial_id': 2}], history)
    assert 'confounded' not in scope
    if changed:
        assert changed in scope and 'learning_rate=' not in scope
    else:
        assert 'matching recorded configurations' in scope


def test_legacy_comparison_does_not_call_an_unknown_default_an_intervention():
    from study.reasoning import observed_scope
    history = [{'trial_id': i+1, 'status': 'completed', 'config': {'model': 'torch_cnn', 'params': params}}
               for i,params in enumerate([{'epochs': 3}, {'epochs': 5, 'learning_rate': .001}])]
    scope = observed_scope([{'trial_id': 1}, {'trial_id': 2}], history)
    assert 'epochs' in scope and 'learning_rate' not in scope and 'confounded' not in scope
    assert 'unknown' in scope.lower()


@pytest.mark.parametrize('change_c', [False, True], ids=['preprocessing-only', 'preprocessing-and-C'])
def test_grounded_preprocessing_scope_counts_independent_settings_with_full_diagnostics(change_c):
    from study.diagnostics import describe_experiment, pipeline_effective_config
    from study.reasoning import LessonMemory, ground_contract, resolve_contract_evidence, validate_contract
    from study.science import build_pipeline

    history = []
    for trial_id, preprocessing, c, score in [(1, 'none', 1., .8),
                                              (2, 'standard', 2. if change_c else 1., .81)]:
        config = {'model': 'logistic', 'preprocessing': preprocessing, 'params': {'C': c}}
        pipeline = build_pipeline(config, seed=42).fit([[-2, 0], [-1, 1], [1, -1], [2, 0]], [0, 0, 1, 1])
        history.append({'trial_id': trial_id, 'status': 'completed', 'config': config,
            'metrics': {'roc_auc': score},
            **describe_experiment(config, problem=None, project={'n_features': 2}, seed=42),
            'actual_effective_config': pipeline_effective_config(pipeline, config, n_features=2)})
    evidence = [{'trial_id': trial_id, 'metric': 'roc_auc'} for trial_id in (1, 2)]
    contract = resolve_contract_evidence({
        'summary': 'The cited trials recorded validation measurements.',
        'what_changed': 'The preprocessing choice changed between the trials.',
        'uncertainty': 'A validation comparison alone does not establish causality.',
        'next_comparison': 'Repeat the comparison with a different model setting.',
        'evidence': evidence,
        'lesson_updates': [{'id': 'scaling', 'status': 'supported',
            'summary': 'The preprocessing settings were compared.',
            'scope': 'Only the cited validation trials were observed.', 'evidence': evidence}]}, history)

    grounded, _ = ground_contract(contract, history)
    assert not validate_contract(grounded, 'reflection', history, memory=True)
    memory = LessonMemory()
    memory.update(grounded['lesson_updates'], history)
    for scope in (grounded['comparison_scope'], grounded['lesson_updates'][0]['scope'],
                  memory.snapshot()[0]['scope']):
        assert 'preprocessing=' in scope
        assert 'preprocessing_params' not in scope
        assert ('confounded' in scope) is change_c
        assert ('C=' in scope) is change_c
