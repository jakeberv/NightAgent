"""Evidence contracts must reject invented measurements and isolate memory."""
import copy
import pytest

from study import controller

HISTORY = [{"trial_id": 1, "status": "completed", "validation_auc": .9,
            "metrics": {"roc_auc": .9}, "config": {"model": "logistic"}}]


def decision():
    return {"hypothesis": "Stronger regularization may improve validation performance.",
            "baseline_trial_id": 1, "change": "Reduce C while retaining the preprocessing.",
            "expected_outcome": "A higher validation score would support stronger regularization.",
            "supervisor_response": "not_applicable", "response_reason": "No supervisor has reviewed this run.",
            "summary": "The researcher is testing stronger regularization against trial 1.",
            "evidence": [{"trial_id": 1, "metric": "roc_auc", "split": "validation", "value": .9}]}


def reasoning():
    # Import inside tests so the first red run reports the missing behavior.
    from study import reasoning
    return reasoning


def test_contract_checks_metric_split_and_value_not_numeric_presence():
    module = reasoning()
    assert module.validate_contract(decision(), "researcher", HISTORY, has_feedback=False) == []
    for key, value in (("trial_id", 5), ("metric", "accuracy"), ("split", "test"), ("value", .95)):
        invalid = decision()
        invalid["evidence"][0][key] = value
        assert module.validate_contract(invalid, "researcher", HISTORY, has_feedback=False)
    failed = copy.deepcopy(HISTORY)
    failed[0]["status"] = "failed"
    assert module.validate_contract(decision(), "researcher", failed, has_feedback=False)


def test_reference_only_citations_resolve_exact_values_without_mutating_input():
    module = reasoning()
    contract = decision()
    del contract['evidence'][0]['value']
    contract['lesson_updates'] = [{'id': 'baseline', 'status': 'supported',
        'summary': 'The baseline performed well.', 'scope': 'Only this validation split was measured.',
        'evidence': copy.deepcopy(contract['evidence'])}]
    original = copy.deepcopy(contract)
    resolved = module.resolve_contract_evidence(contract, HISTORY)
    assert contract == original
    assert resolved['evidence'][0]['value'] == .9
    assert resolved['lesson_updates'][0]['evidence'][0]['value'] == .9
    assert module.validate_contract(resolved, 'researcher', HISTORY, memory=True) == []
    assert module.validate_contract(contract, 'researcher', HISTORY, memory=True)


@pytest.mark.parametrize('change', [
    {'trial_id': 99}, {'metric': 'accuracy'}, {'split': 'test'}, {'value': .95},
    {'value': None}, {'value': True}, {'value': float('nan')}, {'trial_id': True},
])
def test_evidence_resolution_rejects_invalid_references_and_supplied_values(change):
    contract = decision()
    del contract['evidence'][0]['value']
    contract['evidence'][0].update(change)
    with pytest.raises(ValueError):
        reasoning().resolve_contract_evidence(contract, HISTORY)


def test_evidence_resolution_rejects_failed_trials_and_accepts_legacy_auc():
    contract = decision()
    del contract['evidence'][0]['value']
    with pytest.raises(ValueError):
        reasoning().resolve_contract_evidence(contract, [{**HISTORY[0], 'status': 'failed'}])
    result = reasoning().resolve_contract_evidence(contract, [
        {'trial_id': 1, 'status': 'completed', 'validation_auc': .9}])
    assert result['evidence'][0]['value'] == .9


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
        'evidence': [{'trial_id': 7, 'metric': 'roc_auc', 'split': 'validation'},
                     {'trial_id': 10, 'metric': 'roc_auc', 'split': 'validation'}]}
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
        invalid = decision()
        invalid[field] = value
        assert module.validate_contract(invalid, "researcher", HISTORY, has_feedback=False)
    assert module.validate_contract(decision(), "researcher", HISTORY, has_feedback=True)


def test_memory_is_bounded_revisable_and_does_not_accept_ungrounded_lessons():
    module = reasoning()
    ledger = module.LessonMemory(limit=2)
    def lesson(identity, status="supported"):
        return {"id": identity, "status": status, "summary": "The linear baseline reached validation AUC 0.9.",
                "scope": "This conclusion applies only to this dataset and split.",
                "evidence": decision()["evidence"]}
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
    schema = completion_tools(controller.tools_for("researcher", config))[0]["function"]["parameters"]
    assert schema["type"] == "object"
    assert not {"oneOf", "allOf", "anyOf"} & schema.keys()
    assert "intent" in schema["required"]
    assert "lesson_updates" not in schema["properties"]["intent"]["properties"]
    config = StudyConfig(decision_protocol="structured_v1", lesson_memory=True)
    schema = controller.tools_for("researcher", config)[0]["function"]["parameters"]
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
