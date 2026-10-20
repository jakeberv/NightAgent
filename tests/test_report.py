"""Report outcomes must retain failures, nonattainers, and unknown accounting."""
import csv
import json
from pathlib import Path

import pytest


def test_interrupted_suite_preserves_planned_runs_in_denominator(tmp_path):
    from study.report import build_report_data
    write_run(tmp_path, "done", trials=[trial("1", 3, .94)])
    (tmp_path / "suite.json").write_text(json.dumps({
        "config": {"allowance_seconds": 100},
        "schedule": [{"run_id": "done", "condition": "researcher_alone", "repeat": 0},
                     {"run_id": "missing", "condition": "researcher_alone", "repeat": 1}]}))
    data = build_report_data(tmp_path)
    assert len(data["runs"]) == 2
    assert data["conditions"]["researcher_alone"]["milestone_fraction"] == .5
    assert data["runs"][1]["best_validation_auc"] is None
    assert data["runs"][1]["total_cost"] is None
    assert any("incomplete" in warning.lower() for warning in data["warnings"])


def test_postrun_timeout_keeps_completed_shared_test_scores_visible(tmp_path):
    from study.report import build_report_data
    write_run(tmp_path, "a", best={"trial_id": "1", "elapsed_seconds": 3,
        "validation_auc": .96, "artifact_hash": "finished"},
        milestone={"trial_id": "2", "elapsed_seconds": 2,
                   "validation_auc": .94, "artifact_hash": "pending"})
    cache = tmp_path / "evaluation"
    cache.mkdir()
    (cache / "test-evaluation-cache.json").write_text(json.dumps({"artifacts": {
        "finished": {"artifact_hash": "finished", "status": "completed", "test_auc": .91},
        "pending": {"artifact_hash": "pending", "status": "in_progress"}}}))
    row = build_report_data(tmp_path)["runs"][0]
    assert row["best_test_auc"] == .91
    assert row["milestone_test_auc"] is None
    assert row["milestone_test_status"] == "uncertain"


def write_run(root, name, *, trials=None, events=None, **overrides):
    folder = root / "runs" / name
    folder.mkdir(parents=True)
    summary = {"run_id": name, "condition": "researcher_alone", "repeat": 1,
               "allowance_seconds": 100, "elapsed_seconds": 20,
               "stop_reason": "trial_cap", "trials": trials or [],
               "best": None, "milestone": None, "stretch": None,
               "accounting": {"known_cost": 0.4, "cost_complete": False,
                              "input_tokens": 80, "output_tokens": 20,
                              "cached_tokens": None, "reasoning_tokens": None,
                              "token_usage_complete": False},
               "config": {"milestone_auc": 0.93, "stretch_auc": 0.95}}
    summary.update(overrides)
    (folder / "summary.json").write_text(json.dumps(summary))
    if events is not None:
        (folder / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
    return folder


def trial(name, seconds, auc, status="completed", compute=1):
    return {"trial_id": name, "elapsed_seconds": seconds, "status": status,
            "validation_auc": auc, "training_seconds": compute}


def test_deadline_outcome_keeps_nonattainers_and_extends_early_stop(tmp_path):
    # A success-only denominator or assigning 100 seconds to failures would fail.
    from study.report import build_report_data
    write_run(tmp_path, "a", trials=[trial("1", 5, .90), trial("2", 10, .94),
                                    trial("3", 110, .99)])
    write_run(tmp_path, "b", trials=[trial("1", 4, .91)])
    write_run(tmp_path, "c", trials=[trial("1", 2, None, "failed")])
    data = build_report_data(tmp_path)
    a, b, c = data["runs"]
    assert a["best_validation_auc"] == .94
    assert a["best_curve"] == [(5., .90), (10., .94), (100., .94)]
    assert b["milestone_reached"] is False
    assert b["milestone_seconds"] is None
    assert c["best_validation_auc"] is None
    assert c["best_curve"] == []
    aggregate = data["conditions"]["researcher_alone"]
    assert aggregate["run_count"] == 3
    assert aggregate["valid_run_count"] == 2
    assert aggregate["milestone_fraction"] == pytest.approx(1/3)
    assert aggregate["stretch_fraction"] == 0
    assert aggregate["milestone_curve"] == [(0., 0.), (10., 1/3), (100., 1/3)]


def test_event_results_use_completion_time_and_test_results_stay_separate(tmp_path):
    from study.report import build_report_data
    folder = write_run(tmp_path, "events", events=[
        {"type": "trial_finished", "trial_id": "one", "elapsed_seconds": 8,
         "result": {"status": "completed", "validation_auc": .96, "elapsed_seconds": 2}},
        {"type": "trial_finished", "trial_id": "two", "elapsed_seconds": 9,
         "result": {"status": "failed", "validation_auc": .99}},
        {"type": "trial_finished", "trial_id": "late", "elapsed_seconds": 101,
         "result": {"status": "completed", "validation_auc": .999}},
    ])
    (folder / "test-results.json").write_text(json.dumps({"best": {"test_auc": .87},
                                                         "milestone": {"test_auc": .87}}))
    row = build_report_data(tmp_path)["runs"][0]
    assert row["best_validation_auc"] == .96
    assert row["milestone_seconds"] == 8
    assert row["stretch_seconds"] == 8
    assert row["best_test_auc"] == .87
    assert row["known_cost"] == .4
    assert row["total_cost"] is None
    assert row["input_tokens"] == 80
    assert row["total_tokens"] is None


def test_discovery_single_run_and_recursive_run_folders_avoids_report_copies(tmp_path):
    from study.report import build_report_data
    folder = write_run(tmp_path, "nested/a", best={"trial_id": "1", "elapsed_seconds": 3,
                                                   "validation_auc": .92})
    report_copy = tmp_path / "reports" / "old"
    report_copy.mkdir(parents=True)
    (report_copy / "summary.json").write_text((folder / "summary.json").read_text())
    assert len(build_report_data(tmp_path)["runs"]) == 1
    assert build_report_data(folder)["runs"][0]["best_validation_auc"] == .92


def test_report_csv_is_portable_unknowns_blank_and_html_is_self_contained(tmp_path):
    from study.report import generate_report
    write_run(tmp_path, "x", condition='<script>alert("x")</script>',
              trials=[trial("1", 10, .94)],
              postrun_accounting={"evaluation_seconds": 2, "known_cost": 0})
    output = generate_report(tmp_path)
    assert output == tmp_path / "report.html"
    html = output.read_text()
    assert '<script>alert("x")</script>' not in html
    assert '&lt;script&gt;' in html
    assert 'data:image/png;base64,' in html
    assert '<script src=' not in html
    assert 'Training/tool compute' in html
    assert 'Post-run evaluation/reporting' in html
    assert 'unknown' in html.lower()
    with (tmp_path / "summary.csv").open(newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["milestone_seconds"] == "10.0"
    assert row["stretch_seconds"] == ""
    assert row["total_cost"] == ""
    assert row["best_validation_auc"] == "0.94"
    assert row["best_test_auc"] == ""


def test_nested_science_results_and_postrun_metering(tmp_path):
    from study.report import build_report_data
    folder = write_run(tmp_path, "nested", trials=[trial("one", 20, .94)], training_seconds=7)
    (folder / "test-results.json").write_text(json.dumps({
        "selections": {"best": {"status": "completed", "test_auc": .88},
                       "milestone": {"status": "uncertain", "error": "interrupted"}},
        "artifacts": {"abc": {"status": "completed", "test_auc": .88}}}))
    (folder / "postrun.json").write_text(json.dumps({"evaluation_seconds": 3.5}))
    row = build_report_data(tmp_path)["runs"][0]
    assert row["best_test_auc"] == .88
    assert row["milestone_test_auc"] is None
    assert row["milestone_test_status"] == "uncertain"
    assert row["training_seconds"] == 7
    assert row["evaluation_seconds"] == 3.5
    assert row["reporting_seconds"] is None


def test_ties_keep_earliest_completion_and_empty_run_stays_in_denominator(tmp_path):
    from study.report import build_report_data
    write_run(tmp_path, "a", trials=[trial("later", 20, .95), trial("earlier", 10, .95)])
    write_run(tmp_path, "b", stop_reason="not_started")
    data = build_report_data(tmp_path)
    assert data["runs"][0]["best_trial_id"] == "earlier"
    assert data["runs"][1]["milestone_seconds"] is None
    assert data["conditions"]["researcher_alone"]["milestone_fraction"] == .5
    assert data["conditions"]["researcher_alone"]["stretch_fraction"] == .5


def test_controller_integer_attempt_count_and_frozen_thresholds(tmp_path):
    from study.report import build_report_data
    write_run(tmp_path, "controller", trials=3, config={"milestone": .90, "stretch": .92},
              events=[{"type": "trial_finished", "elapsed_seconds": 15,
                       "result": {"trial_id": 1, "elapsed_seconds": 14.99,
                                  "duration_seconds": 2, "status": "completed", "validation_auc": .91}}])
    row = build_report_data(tmp_path)["runs"][0]
    assert row["trial_attempts"] == 3
    assert row["milestone_auc"] == .90
    assert row["milestone_seconds"] == 14.99
    assert row["stretch_reached"] is False
    assert row["training_seconds"] == 2


def test_unknown_cached_and_reasoning_details_are_not_zero_totals(tmp_path):
    from study.report import build_report_data
    write_run(tmp_path, "details", accounting={"known_cost": .1, "cost_complete": True,
              "input_tokens": 30, "output_tokens": 10, "token_usage_complete": True,
              "cached_tokens": 0, "reasoning_tokens": 0,
              "cached_tokens_complete": False, "reasoning_tokens_complete": False})
    row = build_report_data(tmp_path)["runs"][0]
    assert row["total_tokens"] == 40
    assert row["cached_tokens"] is None
    assert row["reasoning_tokens"] is None
    assert row["total_cost"] == .1


def test_suite_postrun_cost_is_separate_from_search(tmp_path):
    from study.report import build_report_data
    write_run(tmp_path, "a")
    (tmp_path / "postrun.json").write_text(json.dumps({"evaluation_seconds": 12,
          "reporting_seconds": 3, "model_cost": 0, "note": "outside search"}))
    data = build_report_data(tmp_path)
    assert data["postrun_accounting"]["evaluation_seconds"] == 12
    assert data["postrun_accounting"]["reporting_seconds"] == 3
    assert data["runs"][0]["known_cost"] == .4
    assert data["runs"][0]["total_cost"] is None
