"""Evidence contracts must reject invented measurements and isolate memory."""
import copy
import pytest

from study import model_tools

HISTORY = [{"trial_id": 1, "status": "completed", "validation_auc": .9,
            "metrics": {"roc_auc": .9}, "config": {"model": "logistic"}}]


def decision():
    return {"hypothesis": "Stronger regularization may improve validation performance.",
            "baseline_trial_id": 1, "change": "Reduce C while retaining the preprocessing.",
            "expected_outcome": "A higher validation score would support stronger regularization.",
            "supervisor_response": "not_applicable", "response_reason": "No supervisor has reviewed this run.",
            "summary": "The researcher is testing stronger regularization against trial 1.",
            "evidence": [{"trial_id": 1, "metric": "roc_auc"}]}


def recorded_decision():
    contract = decision()
    contract['evidence'] = [{'trial_id': 1, 'metric': 'roc_auc', 'split': 'validation', 'value': .9}]
    return contract


def reasoning():
    # Import inside tests so the first red run reports the missing behavior.
    from study import reasoning
    return reasoning


def test_contract_checks_metric_split_and_value_not_numeric_presence():
    module = reasoning()
    assert module.validate_contract(recorded_decision(), "researcher", HISTORY, has_feedback=False) == []
    for key, value in (("trial_id", 5), ("metric", "accuracy"), ("split", "test"), ("value", .95)):
        invalid = recorded_decision()
        invalid["evidence"][0][key] = value
        assert module.validate_contract(invalid, "researcher", HISTORY, has_feedback=False)
    failed = copy.deepcopy(HISTORY)
    failed[0]["status"] = "failed"
    assert module.validate_contract(recorded_decision(), "researcher", failed, has_feedback=False)


def test_reference_only_citations_resolve_exact_values_without_mutating_input():
    module = reasoning()
    contract = decision()
    contract['lesson_updates'] = [{'id': 'baseline', 'status': 'supported',
        'summary': 'The baseline performed well.', 'scope': 'Only this validation split was measured.',
        'evidence': contract['evidence']}]
    original = copy.deepcopy(contract)
    resolved = module.resolve_contract_evidence(contract, HISTORY)
    assert contract == original
    assert resolved['evidence'] == [{'trial_id': 1, 'metric': 'roc_auc', 'split': 'validation', 'value': .9}]
    assert resolved['lesson_updates'][0]['evidence'] == resolved['evidence']
    assert module.validate_contract(resolved, 'researcher', HISTORY, memory=True) == []
    assert module.validate_contract(contract, 'researcher', HISTORY, memory=True)


@pytest.mark.parametrize('change', [
    {'trial_id': 99}, {'metric': 'accuracy'}, {'split': 'test'}, {'value': .95},
    {'value': None}, {'value': True}, {'value': float('nan')}, {'trial_id': True},
    {'value': .9}, {'split': 'validation'},
])
def test_evidence_resolution_rejects_invalid_references_and_supplied_values(change):
    contract = decision()
    contract['evidence'][0].update(change)
    with pytest.raises(ValueError):
        reasoning().resolve_contract_evidence(contract, HISTORY)


def test_evidence_resolution_requires_completed_named_metrics():
    contract = decision()
    with pytest.raises(ValueError):
        reasoning().resolve_contract_evidence(contract, [{**HISTORY[0], 'status': 'failed'}])
    with pytest.raises(ValueError):
        reasoning().resolve_contract_evidence(contract, [
            {'trial_id': 1, 'status': 'completed', 'validation_auc': .9}])


def test_model_contract_schema_accepts_only_references_and_recorded_schema_requires_measurements():
    module = reasoning()
    request_schema = module.request_contract_schema('researcher', memory=True)
    assert module.schema_errors(decision(), request_schema, 'request') == []
    assert module.schema_errors(recorded_decision(), request_schema, 'request')
    assert module.schema_errors(decision(), module.contract_schema('researcher'), 'record')
    assert module.schema_errors(recorded_decision(), module.contract_schema('researcher'), 'record') == []
    for field in ('value', 'split'):
        invalid = recorded_decision()
        del invalid['evidence'][0][field]
        assert module.validate_contract(invalid, 'researcher', HISTORY)


@pytest.mark.parametrize('value', [.9, .95])
def test_lesson_requests_cannot_supply_measurements_even_when_correct(value):
    contract = decision()
    contract['lesson_updates'] = [{'id': 'baseline', 'status': 'supported',
        'summary': 'The baseline was measured.', 'scope': 'Only this validation split was measured.',
        'evidence': [{'trial_id': 1, 'metric': 'roc_auc', 'value': value}]}]
    with pytest.raises(ValueError, match='value'):
        reasoning().resolve_contract_evidence(contract, HISTORY)


def test_model_cannot_supply_the_harness_interpretation_label():
    contract = decision()
    contract['lesson_updates'] = [{'id': 'baseline', 'status': 'supported',
        'summary': 'The baseline was measured.', 'scope': 'Only this validation split was measured.',
        'evidence': decision()['evidence'],
        'interpretation': {'status': 'unverified', 'summary': 'A supplied interpretation.',
                           'scope': 'This interpretation is supplied by the model.'}}]
    assert reasoning().schema_errors(contract, reasoning().request_contract_schema('researcher', True), 'request')


def test_memory_requires_resolved_evidence_instead_of_accepting_model_requests():
    lesson = {'id': 'baseline', 'status': 'supported', 'summary': 'A baseline was measured.',
              'scope': 'Only this validation split was measured.', 'evidence': decision()['evidence']}
    with pytest.raises((ValueError, reasoning().jsonschema.ValidationError)):
        reasoning().LessonMemory().update([lesson], HISTORY)


def test_lessons_use_recorded_scores_and_all_changed_parameters_as_facts():
    history = [
        {'trial_id': 7, 'status': 'completed', 'metrics': {'roc_auc': .9308},
         'config': {'model': 'histogram_gradient_boosting', 'preprocessing': 'standard',
                    'params': {'learning_rate': .1, 'max_iter': 300, 'max_leaf_nodes': 63}}},
        {'trial_id': 10, 'status': 'completed', 'metrics': {'roc_auc': .9317},
         'config': {'model': 'histogram_gradient_boosting', 'preprocessing': 'standard',
                    'params': {'learning_rate': .05, 'max_iter': 400, 'max_leaf_nodes': 63}}},
    ]
    lesson = {'id': 'learning-rate', 'status': 'supported',
        'summary': 'Slower learning improves generalization.',
        'scope': 'Only learning_rate differs between these trials.',
        'evidence': [{'trial_id': 7, 'metric': 'roc_auc', 'split': 'validation', 'value': .9308},
                     {'trial_id': 10, 'metric': 'roc_auc', 'split': 'validation', 'value': .9317}]}
    ledger = reasoning().LessonMemory()
    ledger.update([lesson], history)
    stored = ledger.snapshot()[0]
    assert '0.9308' in stored['summary'] and '0.9317' in stored['summary']
    assert 'learning_rate' in stored['scope'] and 'max_iter' in stored['scope']
    assert 'confound' in stored['scope'] or 'not isolated' in stored['scope']
    assert stored['summary'] != lesson['summary'] and stored['scope'] != lesson['scope']
    assert stored['interpretation'] == {'status': 'unverified',
        'summary': lesson['summary'], 'scope': lesson['scope']}
    assert all(len(stored[field]) <= 240 and stored[field].endswith('.') for field in ('summary', 'scope'))
    assert all('value' in citation for citation in stored['evidence'])
    ledger.update([stored], history)
    assert ledger.snapshot() == [stored]


def test_contract_requires_full_sentences_baseline_and_honest_feedback_status():
    module = reasoning()
    for field, value in (("summary", "Testing stronger regularization"),
                         ("baseline_trial_id", 999), ("supervisor_response", "followed")):
        invalid = recorded_decision()
        invalid[field] = value
        assert module.validate_contract(invalid, "researcher", HISTORY, has_feedback=False)
    assert module.validate_contract(recorded_decision(), "researcher", HISTORY, has_feedback=True)


def test_memory_is_bounded_revisable_and_does_not_accept_ungrounded_lessons():
    module = reasoning()
    ledger = module.LessonMemory(limit=2)
    def lesson(identity, status="supported"):
        return {"id": identity, "status": status, "summary": "The linear baseline reached validation AUC 0.9.",
                "scope": "This conclusion applies only to this dataset and split.",
                "evidence": recorded_decision()["evidence"]}
    ledger.update([lesson("linear")], HISTORY)
    ledger.update([lesson("linear", "superseded"), lesson("second")], HISTORY)
    ledger.update([lesson("third")], HISTORY)
    assert [entry["id"] for entry in ledger.snapshot()] == ["second", "third"]
    invalid = lesson("bad")
    invalid["evidence"][0]["value"] = .99
    with pytest.raises(ValueError):
        ledger.update([lesson("valid"), invalid], HISTORY)
    assert [entry["id"] for entry in ledger.snapshot()] == ["second", "third"]
    assert module.LessonMemory(limit=2).snapshot() == []


def test_structured_tool_schema_keeps_anthropic_compatible_root():
    from study.config import StudyConfig
    config = StudyConfig(decision_protocol="structured_v1")
    from study.provider import completion_tools
    schema = completion_tools(model_tools.tools_for("researcher", config))[0]["function"]["parameters"]
    assert schema["type"] == "object"
    assert not {"oneOf", "allOf", "anyOf"} & schema.keys()
    assert "intent" in schema["required"]
    assert "lesson_updates" not in schema["properties"]["intent"]["properties"]
    config = StudyConfig(decision_protocol="structured_v1", lesson_memory=True)
    schema = model_tools.tools_for("researcher", config)[0]["function"]["parameters"]
    assert "lesson_updates" in schema["properties"]["intent"]["properties"]


def test_structured_contract_is_default_and_legacy_runtime_is_rejected():
    from study.config import StudyConfig
    assert StudyConfig().decision_protocol == "structured_v1"
    assert StudyConfig(lesson_memory=True).lesson_memory
    with pytest.raises(ValueError, match="structured"):
        StudyConfig(decision_protocol="legacy")


def test_length_repairs_report_all_limits_without_echoing_long_responses():
    contract = decision()
    contract.update(summary="Long summary " * 50 + ".", hypothesis="Long hypothesis " * 50 + ".")
    errors = reasoning().validate_contract(contract, "researcher", HISTORY)
    assert any("summary" in error and "240" in error for error in errors)
    assert any("hypothesis" in error and "500" in error for error in errors)
    assert sum(map(len, errors)) < 400


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "1"])
def test_model_start_buffer_requires_finite_nonnegative_seconds(value):
    from study.config import StudyConfig
    with pytest.raises(ValueError, match="model_start_buffer_seconds"):
        StudyConfig(model_start_buffer_seconds=value)
