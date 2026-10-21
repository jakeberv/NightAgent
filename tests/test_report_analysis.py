"""Report analysis must preserve unknowns and the matched experimental unit."""
import json

import pytest

from study.report import build_report_data, generate_report
from test_report import write_run, trial


def frozen_config(condition, repeat=0, **changes):
    return {"condition": condition, "repeat": repeat, "training_seed": 42 + repeat,
            "model": "fixed", "allowance_seconds": 100, "lesson_memory": False,
            "decision_protocol": "structured_v1", **changes}


def paired_run(root, name, condition, repeat=0, score=.8, **config_changes):
    return write_run(root, name, condition=condition, repeat=repeat,
        trials=[] if score is None else [trial("1", 10, score)],
        problem_hash="problem", data_fingerprint="data",
        config=frozen_config(condition, repeat, **config_changes))


def test_role_metrics_count_failed_retries_cancelled_and_unfinished_calls(tmp_path):
    calls = []
    for status, usage, seconds in [
        ("failed", {"prompt_tokens": 10, "completion_tokens": 2, "cost": .1}, 2),
        ("completed", {"prompt_tokens": 20, "completion_tokens": 5, "cost": .2,
          "prompt_tokens_details": {"cached_tokens": 8},
          "completion_tokens_details": {"reasoning_tokens": 3}}, 3),
        ("cancelled", None, 4),
    ]:
        calls.extend([{"type": "model_call_started", "role": "researcher"},
                      {"type": "model_call", "role": "researcher", "status": status,
                       "usage": usage, "duration_seconds": seconds}])
    calls.extend([{"type": "model_call_started", "role": "supervisor"},
                  {"type": "model_call_started", "role": "reflection"},
                  {"type": "model_call", "role": "reflection", "status": "completed",
                   "duration_seconds": 1, "usage": {"prompt_tokens": 6, "completion_tokens": 4,
                   "cost": 0, "prompt_tokens_details": {"cached_tokens": 5},
                   "completion_tokens_details": {"reasoning_tokens": 2}}}])
    write_run(tmp_path, "roles", events=calls)
    roles = build_report_data(tmp_path)["runs"][0].get("role_metrics")
    assert roles is not None, "Reports need per-role attempt and accounting totals."
    researcher = roles["researcher"]
    assert researcher["attempts"] == 3
    assert researcher["failed"] == 1 and researcher["cancelled"] == 1
    assert researcher["failure_fraction"] == pytest.approx(2 / 3)
    assert researcher["known_cost"] == pytest.approx(.3)
    assert researcher["total_cost"] is None and researcher["total_tokens"] is None
    assert researcher["input_tokens"] == 30 and researcher["output_tokens"] == 7
    assert researcher["model_seconds"] == 9
    assert roles["supervisor"]["unfinished"] == 1
    assert roles["supervisor"]["known_cost"] is None
    assert roles["supervisor"]["model_seconds"] is None
    assert roles["reflection"]["total_tokens"] == 10
    assert roles["reflection"]["total_cost"] == 0


def test_recommendation_uptake_separates_invalid_contracts_and_observed_outcomes(tmp_path):
    events = [{"type": "decision_contract", "valid": True, "trial_id": "2",
               "contract": {"baseline_trial_id": "1", "supervisor_response": "followed"}},
              {"type": "decision_contract", "valid": True, "trial_id": "3",
               "contract": {"baseline_trial_id": "1", "supervisor_response": "modified"}},
              {"type": "decision_contract", "valid": False, "trial_id": "4",
               "contract": {"supervisor_response": "followed"}},
              {"type": "decision_contract", "valid": True, "trial_id": "5",
               "contract": {"supervisor_response": "not_applicable"}}]
    write_run(tmp_path, "uptake", events=events, trials=[trial("1", 1, .7), trial("2", 2, .8),
                                                         trial("3", 3, None, "failed")])
    uptake = build_report_data(tmp_path)["runs"][0].get("recommendation_uptake")
    assert uptake is not None, "Reports need explicit recommendation response counts."
    assert uptake["applicable"] == 2 and uptake["followed"] == 1 and uptake["modified"] == 1
    assert uptake["invalid"] == 1 and uptake["not_applicable"] == 1
    assert uptake["followed_fraction"] == .5
    assert uptake["outcomes"][0]["validation_delta"] == pytest.approx(.1)
    assert uptake["outcomes"][1]["validation_delta"] is None
    assert uptake["outcomes"][1]["trial_status"] == "failed"


def test_paired_comparisons_use_repeat_differences_and_keep_failure_denominators(tmp_path):
    for repeat, scores in enumerate([(.7, .8), (.75, .95), (None, .85)]):
        paired_run(tmp_path, f"a{repeat}", "researcher_alone", repeat, scores[0])
        paired_run(tmp_path, f"b{repeat}", "frequent", repeat, scores[1])
    data = build_report_data(tmp_path)
    assert "paired_comparisons" in data, "Reports need matched-repeat condition comparisons."
    comparison, = data["paired_comparisons"]
    assert comparison["condition_a"] == "researcher_alone"
    assert comparison["condition_b"] == "frequent"
    assert comparison["matched_pairs"] == 3
    assert comparison["missing_score_pairs"] == 1
    assert comparison["no_valid_model_a"] == 1 and comparison["no_valid_model_b"] == 0
    score = comparison["metrics"]["best_score"]
    assert score["n"] == 2 and score["mean_delta"] == pytest.approx(.15)
    assert score["ci95"] == pytest.approx([-.48531024, .78531024])
    assert comparison["metrics"]["total_cost"]["n"] == 0
    assert comparison["metrics"]["total_cost"]["mean_delta"] is None


def test_one_pair_has_no_ci_and_memory_variants_are_never_pooled(tmp_path):
    for name, memory in [("off", False), ("on", True)]:
        paired_run(tmp_path, "a" + name, "researcher_alone", lesson_memory=memory)
        paired_run(tmp_path, "b" + name, "frequent", score=.9, lesson_memory=memory)
    data = build_report_data(tmp_path)
    comparisons = data.get("paired_comparisons", [])
    assert len(comparisons) == 2
    assert {c["config"]["lesson_memory"] for c in comparisons} == {False, True}
    assert all(c["metrics"]["best_score"]["ci95"] is None for c in comparisons)
    assert len(data["conditions"]) == 4


def test_grounded_policy_runs_are_not_pooled_with_historical_reasoning(tmp_path):
    paired_run(tmp_path, 'before', 'periodic_reflection', lesson_memory=True)
    paired_run(tmp_path, 'after', 'periodic_reflection', lesson_memory=True,
               reasoning_policy='grounded_v1')
    data = build_report_data(tmp_path)
    assert len(data['conditions']) == 2


@pytest.mark.parametrize("change", [{"training_seed": 999}, {"model": "other"},
                                     {"decision_protocol": "legacy"}, {"lesson_memory": True},
                                     {"reasoning_policy": "grounded_v1"}])
def test_mismatched_config_or_seed_cannot_form_a_pair(tmp_path, change):
    paired_run(tmp_path, "a", "researcher_alone")
    paired_run(tmp_path, "b", "frequent", **change)
    data = build_report_data(tmp_path)
    assert "paired_comparisons" in data
    assert not any(c["matched_pairs"] for c in data["paired_comparisons"])


def test_missing_identity_and_duplicate_units_do_not_create_pairs(tmp_path):
    paired_run(tmp_path, "a", "researcher_alone")
    paired_run(tmp_path, "duplicate", "researcher_alone")
    paired_run(tmp_path, "b", "frequent")
    data = build_report_data(tmp_path)
    assert "paired_comparisons" in data
    assert not any(c["matched_pairs"] for c in data["paired_comparisons"])
    assert any("duplicate" in warning.lower() for warning in data["warnings"])
    for path in (tmp_path / "runs").glob("*/summary.json"):
        summary = json.loads(path.read_text())
        summary.pop("data_fingerprint")
        path.write_text(json.dumps(summary))
    assert not build_report_data(tmp_path)["paired_comparisons"]


def test_report_exports_analysis_tables_and_role_graphic_without_inventing_legacy_data(tmp_path):
    paired_run(tmp_path, "a", "researcher_alone")
    b = paired_run(tmp_path, "b", "frequent", score=.9)
    (b / "events.jsonl").write_text(json.dumps({"type": "model_call", "role": "supervisor",
        "status": "completed", "duration_seconds": 2, "usage": {"cost": .2}}))
    report = generate_report(tmp_path).read_text()
    assert "Matched condition comparisons" in report
    assert "Recommendation uptake" in report
    assert "API usage by role" in report
    assert (tmp_path / "figures" / "roles.svg").exists()
    assert (tmp_path / "figures" / "paired.svg").exists()
    assert (tmp_path / "paired-comparisons.json").exists()
    run = build_report_data(tmp_path)["runs"][0]
    assert run["role_metrics"] == {}
    assert run["recommendation_uptake"]["followed_fraction"] is None


def test_unknown_protocol_stays_unknown_and_never_matches_structured(tmp_path):
    path = paired_run(tmp_path, "old", "researcher_alone") / "summary.json"
    summary = json.loads(path.read_text())
    summary["config"].pop("decision_protocol")
    path.write_text(json.dumps(summary))
    paired_run(tmp_path, "new", "frequent")
    data = build_report_data(tmp_path)
    old = next(row for row in data["runs"] if row["run_id"] == "old")
    assert old.get("decision_protocol") is None
    assert not any(c["matched_pairs"] for c in data["paired_comparisons"])


def test_unstarted_scheduled_run_uses_its_planned_seed_and_stays_in_pair_denominator(tmp_path):
    paired_run(tmp_path, "done", "researcher_alone", repeat=1)
    config = frozen_config("researcher_alone")
    (tmp_path / "suite.json").write_text(json.dumps({"config": config, "schedule": [
        {"run_id": "done", "condition": "researcher_alone", "repeat": 1},
        {"run_id": "missing", "condition": "frequent", "repeat": 1}]}))
    # A suite freezes the same scientific identity independently of run summaries.
    manifest = json.loads((tmp_path / "suite.json").read_text())
    manifest.update(problem_hash="problem", data_fingerprint="data",
                    objective={"metric": "roc_auc", "direction": "maximize"},
                    target_definitions=[{"name": "milestone", "value": .93}, {"name": "stretch", "value": .95}])
    (tmp_path / "suite.json").write_text(json.dumps(manifest))
    comparison, = build_report_data(tmp_path)["paired_comparisons"]
    assert comparison["matched_pairs"] == 1
    assert comparison["missing_score_pairs"] == 1
    assert comparison["stop_reasons_b"] == {"not_started": 1}
    assert comparison["no_valid_model_b"] == 1
    assert comparison["metrics"]["best_score"]["ci95"] is None
    assert comparison["targets"]["milestone"]["attainment"]["n"] == 1


def test_literature_availability_without_calls_is_explicitly_unexercised(tmp_path):
    tools = [{"type": "function", "function": {"name": name}} for name in
             ("literature_search", "literature_fetch")]
    write_run(tmp_path, "available", condition="periodic_reflection_literature",
              events=[{"type": "model_call_started", "role": "supervisor", "tools": tools}])
    row = build_report_data(tmp_path)["runs"][0]
    coverage = row.get("literature_coverage")
    assert coverage is not None, "Reports must separate literature availability from exercised retrieval."
    assert coverage["enabled"] is True
    assert coverage["tools_offered"] == ["literature_fetch", "literature_search"]
    assert coverage["state"] == "unexercised"
    assert coverage["search_attempts"] == coverage["fetch_attempts"] == 0
    assert coverage["feedback_source_urls"] == []
    document = generate_report(tmp_path).read_text()
    assert "Literature coverage" in document and "unexercised" in document


def test_literature_coverage_counts_failures_passages_and_only_observed_feedback_urls(tmp_path):
    source = "https://example.org/paper"
    events = [
        {"type": "tool_call", "name": "literature_search", "result": {"results": [
            {"url": source, "title": "Paper", "passage": "Abstract evidence."}]}},
        {"type": "tool_call", "name": "literature_fetch", "result": {"error": "timeout"}},
        {"type": "tool_call", "name": "literature_fetch", "result": {"url": source, "text": "Source passage."}},
        {"type": "review", "feedback": "See https://example.org/paper-other."},
        {"type": "review", "contract": {"summary": f"Use evidence ({source})."}},
    ]
    write_run(tmp_path, "retrieved", condition="periodic_reflection_literature", events=events)
    coverage = build_report_data(tmp_path)["runs"][0].get("literature_coverage")
    assert coverage is not None
    assert coverage["search_attempts"] == coverage["search_successes"] == 1
    assert coverage["fetch_attempts"] == 2 and coverage["fetch_successes"] == 1
    assert coverage["source_passages_retrieved"] == 2
    assert coverage["feedback_source_urls"] == [source]
    assert coverage["state"] == "passage_retrieved"


def test_missing_literature_event_log_retains_unknown_attempts(tmp_path):
    write_run(tmp_path, "legacy", condition="periodic_reflection_literature")
    coverage = build_report_data(tmp_path)["runs"][0].get("literature_coverage")
    assert coverage is not None
    assert coverage["state"] == "unknown"
    assert coverage["search_attempts"] is None
    assert coverage["fetch_attempts"] is None
    assert coverage["feedback_source_urls"] is None


def test_reused_proposal_is_not_counted_as_executed_recommendation_uptake(tmp_path):
    write_run(tmp_path, "reuse", events=[{"type": "decision_contract", "valid": True,
        "executed": False, "trial_id": None, "contract": {"supervisor_response": "followed"}},
        {"type": "experiment_reused", "matched_trial_ids": [1]}])
    row = build_report_data(tmp_path)["runs"][0]
    assert row["recommendation_uptake"]["followed"] == 0
    assert row["recommendation_uptake"]["reused_proposals"] == 1
    assert row["recommendation_uptake"]["outcomes"] == []
    assert row["trace"][1]["type"] == "experiment_reused"


def test_literature_feedback_does_not_credit_prefixes_or_later_retrieval(tmp_path):
    source = "https://example.org/paper"
    write_run(tmp_path, "timing", condition="periodic_reflection_literature", events=[
        {"type": "review", "feedback": source},
        {"type": "tool_call", "name": "literature_fetch", "result": {"url": source, "text": "Evidence"}},
        {"type": "review", "feedback": source + "-other"},
    ])
    coverage = build_report_data(tmp_path)["runs"][0]["literature_coverage"]
    assert coverage["feedback_records"] == 2
    assert coverage["feedback_source_urls"] == []


def test_successful_empty_retrieval_is_not_reported_as_a_source_passage(tmp_path):
    write_run(tmp_path, "empty", condition="periodic_reflection_literature", events=[
        {"type": "tool_call", "name": "literature_search", "result": {"results": []}},
        {"type": "tool_call", "name": "literature_fetch", "result": {"url": "https://example.org", "text": " "}},
    ])
    coverage = build_report_data(tmp_path)["runs"][0]["literature_coverage"]
    assert coverage["search_successes"] == coverage["fetch_successes"] == 1
    assert coverage["search_results"] == coverage["source_passages_retrieved"] == 0
    assert coverage["state"] == "attempted_without_passage"
