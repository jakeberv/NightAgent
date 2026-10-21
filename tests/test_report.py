"""Report outcomes must retain failures, nonattainers, and unknown accounting."""
import csv
import json
from pathlib import Path

import pytest


def test_interrupted_suite_preserves_planned_runs_in_denominator(tmp_path):
    from study.report import build_report_data
    write_run(tmp_path, "done", trials=[trial("1", 3, .94)])
    (tmp_path / "suite.json").write_text(json.dumps({
        "config": {"allowance_seconds": 100, "decision_protocol": "structured_v1"},
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
        "finished": {"artifact_hash": "finished", "status": "completed", "score": .91},
        "pending": {"artifact_hash": "pending", "status": "in_progress"}}}))
    row = build_report_data(tmp_path)["runs"][0]
    assert row["best_test_auc"] == .91
    assert row["milestone_test_auc"] is None
    assert row["milestone_test_status"] == "uncertain"


def write_run(root, name, *, trials=None, events=None, **overrides):
    """Write current frozen summaries and journal results for report scenarios."""
    folder = root / "runs" / name
    folder.mkdir(parents=True)
    summary = {"run_id": name, "condition": "researcher_alone", "repeat": 1,
               "objective": {"metric": "roc_auc", "direction": "maximize"},
               "target_definitions": [{"name": "milestone", "value": .93}, {"name": "stretch", "value": .95}],
               "allowance_seconds": 100, "elapsed_seconds": 20,
               "stop_reason": "trial_cap", "trials": trials if type(trials) is int else len(trials or []),
               "best": None, "target_selections": {},
               "accounting": {"known_cost": 0.4, "cost_complete": False,
                              "input_tokens": 80, "output_tokens": 20,
                              "cached_tokens": None, "reasoning_tokens": None,
                              "token_usage_complete": False},
               "config": {"decision_protocol": "structured_v1"}}
    summary.update(overrides)
    if "target_definitions" not in overrides:
        for target in summary["target_definitions"]:
            target["value"] = summary["config"].get(target["name"], target["value"])
    for target in summary["target_definitions"]:
        if target["name"] in overrides:
            summary["target_selections"][target["name"]] = summary.pop(target["name"])
    recorded = list(events or [])
    observed = list(trials) if isinstance(trials, list) else []
    # Selection-only scenarios explicitly record the selected trial in their
    # fixture journal. Production never reconstructs missing trial evidence.
    if events is None and not observed:
        observed = [value for value in [summary["best"], *summary["target_selections"].values()] if value]
    for result in observed:
        recorded.append({"type": "trial_finished", "elapsed_seconds": result["elapsed_seconds"], "result": result})
    metric = summary["objective"]["metric"]
    for index, event in enumerate(recorded):
        event["schema_version"] = 1
        if event["type"] == "model_call":
            event.setdefault("status", "completed")
        if event["type"] != "trial_finished":
            continue
        result = dict(event["result"])
        result.setdefault("trial_id", event.get("trial_id", index + 1))
        result.setdefault("status", "completed")
        result.setdefault("elapsed_seconds", event.get("elapsed_seconds"))
        if "validation_auc" in result and "score" not in result:
            result["score"] = result["validation_auc"]
            result["metrics"] = {metric: result["score"]} if result["score"] is not None else {}
        event["result"] = result
    identities = {}
    for event in recorded:
        if event["type"] == "trial_finished":
            identity = str(event["result"]["trial_id"])
            identities.setdefault(identity, len(identities) + 1)
    def current_id(value):
        return identities.get(str(value), int(value) if str(value).isdigit() else None)
    for event in recorded:
        if "trial_id" in event and event["trial_id"] is not None:
            event["trial_id"] = current_id(event["trial_id"])
        if event["type"] == "trial_finished":
            event["result"]["trial_id"] = current_id(event["result"]["trial_id"])
        contract = event.get("contract") or {}
        if contract.get("baseline_trial_id") is not None:
            contract["baseline_trial_id"] = current_id(contract["baseline_trial_id"])
    for selection in [summary["best"], *summary["target_selections"].values()]:
        if selection:
            selection["trial_id"] = current_id(selection["trial_id"])
    if type(trials) is not int:
        summary["trials"] = len({str(event["result"]["trial_id"]) for event in recorded if event["type"] == "trial_finished"})
    if "postrun_accounting" in summary:
        (folder / "postrun.json").write_text(json.dumps(summary.pop("postrun_accounting")))
    (folder / "summary.json").write_text(json.dumps(summary))
    if recorded or events is not None:
        (folder / "events.jsonl").write_text("\n".join(json.dumps(e) for e in recorded) + ("\n" if recorded else ""))
    return folder


def trial(name, seconds, auc, status="completed", compute=1):
    return {"trial_id": name, "elapsed_seconds": seconds, "status": status,
            "score": auc, "metrics": {"roc_auc": auc} if auc is not None else {},
            "training_seconds": compute}


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


def test_event_results_use_frozen_completion_time_and_test_results_stay_separate(tmp_path):
    from study.report import build_report_data
    folder = write_run(tmp_path, "events", events=[
        {"type": "trial_finished", "trial_id": "one", "elapsed_seconds": 8,
         "result": {"status": "completed", "validation_auc": .96, "elapsed_seconds": 8, "duration_seconds": 2,
                    "artifact_hash": "observed"}},
        {"type": "trial_finished", "trial_id": "two", "elapsed_seconds": 9,
         "result": {"status": "failed", "validation_auc": .99}},
        {"type": "trial_finished", "trial_id": "late", "elapsed_seconds": 101,
         "result": {"status": "completed", "validation_auc": .999}},
    ])
    (folder / "test-results.json").write_text(json.dumps({"selections": {"best": {"status": "completed", "score": .87, "artifact_hash": "observed"},
                                                         "milestone": {"status": "completed", "score": .87, "artifact_hash": "observed"}}}))
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


def test_report_exports_graphics_and_preserves_missing_resource_measurements(tmp_path):
    from study.report import build_report_data, generate_report
    write_run(tmp_path, 'mixed', trials=5, training_seconds=3, events=[
        {'type': 'trial_finished', 'elapsed_seconds': 5, 'result': {
            'trial_id': 1, 'status': 'completed', 'validation_auc': .94,
            'elapsed_seconds': 5, 'duration_seconds': 4, 'training_seconds': 2, 'queue_seconds': 2}},
        {'type': 'trial_finished', 'elapsed_seconds': 6, 'result': {
            'trial_id': 2, 'status': 'failed', 'duration_seconds': 1, 'training_seconds': 1}},
        {'type': 'trial_finished', 'elapsed_seconds': 7, 'result': {
            'trial_id': 3, 'status': 'timeout'}},
        {'type': 'trial_finished', 'elapsed_seconds': 110, 'result': {
            'trial_id': 4, 'status': 'completed', 'validation_auc': .99,
            'elapsed_seconds': 110, 'duration_seconds': 1}},
        {'type': 'model_call_started'},
        {'type': 'model_call', 'duration_seconds': 4},
        {'type': 'model_call_started'},
    ])
    row = build_report_data(tmp_path)['runs'][0]
    assert row['trial_outcomes'] == {'Completed': 1, 'Failed': 1, 'Timed out': 1,
                                     'Late': 1, 'Other / unknown': 1}
    assert row['model_seconds'] == 4
    assert row['model_seconds_complete'] is False
    assert row['queue_seconds'] == 2
    assert row['queue_seconds_complete'] is False
    document = generate_report(tmp_path).read_text()
    for name in ('performance', 'workflow'):
        png = tmp_path / 'figures' / f'{name}.png'
        svg = tmp_path / 'figures' / f'{name}.svg'
        assert png.read_bytes().startswith(b'\x89PNG')
        assert '<svg' in svg.read_text()
        assert f'figures/{name}.svg' in document
    assert document.count('data:image/png;base64,') == 4
    assert 'figures/roles.svg' in document
    assert 'incomplete' in document
    assert json.loads((tmp_path / 'report-accounting.json').read_text())['api_calls'] == 0


def test_unrecorded_resource_durations_are_unknown_not_zero(tmp_path):
    from study.report import build_report_data
    write_run(tmp_path, 'unmeasured', trials=[trial('1', 3, .9)])
    row = build_report_data(tmp_path)['runs'][0]
    assert row['model_seconds'] is None
    assert row['queue_seconds'] is None


def test_interrupted_trial_keeps_training_time_labeled_as_subtotal(tmp_path):
    from study.report import build_report_data
    write_run(tmp_path, 'interrupted', trials=2, training_seconds=4, events=[
        {'type': 'trial_finished', 'elapsed_seconds': 6, 'result': {
            'trial_id': 1, 'status': 'completed', 'validation_auc': .94,
            'elapsed_seconds': 6, 'duration_seconds': 5, 'training_seconds': 4}},
        {'type': 'trial_started', 'trial_id': 2},
    ])
    row = build_report_data(tmp_path)['runs'][0]
    assert row['training_seconds'] == 4
    assert row['training_seconds_complete'] is False


def test_nested_science_results_and_postrun_metering(tmp_path):
    from study.report import build_report_data
    folder = write_run(tmp_path, "nested", trials=[{**trial("one", 20, .94), "artifact_hash": "abc"}], training_seconds=7)
    (folder / "test-results.json").write_text(json.dumps({
        "selections": {"best": {"status": "completed", "score": .88, "artifact_hash": "abc"},
                       "milestone": {"status": "uncertain", "error": "interrupted", "artifact_hash": "abc"}},
        "artifacts": {"abc": {"status": "completed", "score": .88}}}))
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
    assert data["runs"][0]["best_trial_id"] == "2"
    assert data["runs"][1]["milestone_seconds"] is None
    assert data["conditions"]["researcher_alone"]["milestone_fraction"] == .5
    assert data["conditions"]["researcher_alone"]["stretch_fraction"] == .5


def test_controller_integer_attempt_count_and_frozen_thresholds(tmp_path):
    from study.report import build_report_data
    write_run(tmp_path, "controller", trials=3, config={"milestone": .90, "stretch": .92},
              events=[{"type": "trial_finished", "elapsed_seconds": 15,
                       "result": {"trial_id": 1, "elapsed_seconds": 14.99,
                                  "duration_seconds": 2, "training_seconds": 2, "status": "completed", "validation_auc": .91}}])
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


def generic_trial(name, seconds, score, metric="rmse", **extra):
    return {"trial_id": name, "elapsed_seconds": seconds, "status": "completed",
            "score": score, "metrics": {metric: score}, **extra}


def generic_summary(metric="rmse", direction="minimize", digest="regression-v1", **extra):
    return {"objective": {"metric": metric, "direction": direction},
            "problem_hash": digest, "problem": {"id": digest},
            "target_definitions": [{"name": "usable model", "value": 5.0}],
            "target_selections": {}, **extra}


def test_rmse_minimizes_scores_above_one_and_uses_named_first_crossings(tmp_path):
    from study.report import build_report_data
    account = {"known_cost": .2, "cost_complete": False}
    selection = generic_trial("first", 10, 4.0, artifact="first.joblib", artifact_hash="abc", accounting=account)
    write_run(tmp_path, "rmse", trials=[generic_trial("worse", 2, 8.0),
              generic_trial("tie", 30, 4.0), selection, generic_trial("late", 101, 1.0)],
              **generic_summary(best=selection, target_selections={"usable model": selection}))
    data = build_report_data(tmp_path)
    row = data["runs"][0]
    assert row["best_score"] == 4.0
    assert row["best_trial_id"] == "3"
    assert row["best_metrics"] == {"rmse": 4.0}
    assert row["best_curve"] == [(2., 8.), (10., 4.), (100., 4.)]
    assert row["targets"]["usable model"]["seconds"] == 10
    assert row["targets"]["usable model"]["artifact_hash"] == "abc"
    assert row["targets"]["usable model"]["total_cost"] is None
    assert "best_validation_auc" not in row
    assert set(row["targets"]) == {"usable model"}
    assert data["objective"] == {"metric": "rmse", "direction": "minimize"}
    assert data["problem_hash"] == "regression-v1"


def test_generic_suite_includes_unstarted_runs_and_shared_partial_test_cache(tmp_path):
    from study.report import build_report_data
    selection = generic_trial("one", 8, 3.0, artifact_hash="done")
    metadata = generic_summary(target_definitions=[{"name": "good", "value": 4}, {"name": "great", "value": 2}])
    write_run(tmp_path, "done", **{**metadata, "best": selection,
              "target_selections": {"good": selection, "great": None}})
    (tmp_path / "suite.json").write_text(json.dumps({**metadata,
        "config": {"allowance_seconds": 100, "decision_protocol": "structured_v1"}, "schedule": [
        {"run_id": "done", "condition": "researcher_alone", "repeat": 0},
        {"run_id": "missing", "condition": "researcher_alone", "repeat": 1}]}))
    cache = tmp_path / "evaluation"
    cache.mkdir()
    (cache / "test-evaluation-cache.json").write_text(json.dumps({"artifacts": {
        "done": {"artifact_hash": "done", "status": "completed", "score": 3.5, "metrics": {"rmse": 3.5}}}}))
    data = build_report_data(tmp_path)
    done, missing = data["runs"]
    assert done["best_test_score"] == 3.5
    assert done["targets"]["good"]["test_score"] == 3.5
    assert done["best_score"] == 3.0
    assert missing["best_score"] is None
    assert missing["targets"]["good"]["seconds"] is None
    assert missing["total_cost"] is None
    assert data["conditions"]["researcher_alone"]["targets"]["good"]["fraction"] == .5
    assert data["conditions"]["researcher_alone"]["best_score_mean"] == 3.0


def test_multiclass_accuracy_report_labels_and_csv_are_generic(tmp_path):
    from study.report import generate_report
    folder = write_run(tmp_path, "multiclass", trials=[generic_trial("one", 10, .96, "accuracy", artifact_hash="multiclass")],
        **generic_summary("accuracy", "maximize", "mnist", target_definitions=[{"name": "publish", "value": .95}]))
    (folder / "test-results.json").write_text(json.dumps({"selections": {
        "best": {"status": "completed", "score": .94, "metrics": {"accuracy": .94, "macro_f1": .93}, "artifact_hash": "multiclass"},
        "publish": {"status": "uncertain", "score": .97, "artifact_hash": "multiclass"}}}))
    output = generate_report(tmp_path)
    html = output.read_text()
    assert "accuracy" in html and "maximize" in html and "publish" in html
    assert "ROC-AUC" not in html and "Milestone" not in html
    with (tmp_path / "summary.csv").open(newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["best_score"] == "0.96"
    assert row["best_test_score"] == "0.94"
    assert "best_validation_auc" not in row
    targets = json.loads(row["targets"])
    assert targets["publish"]["test_score"] is None
    assert targets["publish"]["test_status"] == "uncertain"


def test_multiclass_auc_report_preserves_explicit_metric_and_targets(tmp_path):
    from study.report import generate_report
    metric = "roc_auc_ovr_macro"
    write_run(tmp_path, "multiclass", trials=[generic_trial("one", 10, .96, metric)],
        **generic_summary(metric, "maximize", "mnist-auc",
            target_definitions=[{"name": "milestone", "value": .93}, {"name": "stretch", "value": .95}]))
    html = generate_report(tmp_path).read_text()
    assert "ROC-AUC (macro one-vs-rest)" in html
    assert "not classification accuracy" in html
    with (tmp_path / "summary.csv").open(newline="") as handle:
        row = next(csv.DictReader(handle))
    assert json.loads(row["objective"])["metric"] == metric
    assert row["best_score"] == "0.96"
    assert json.loads(row["targets"])["stretch"]["reached"]


@pytest.mark.parametrize("other", [generic_summary(digest="other-data"),
    generic_summary("accuracy", "maximize", "regression-v1"),
    {"objective": {"metric": "rmse", "direction": "maximize"}, "problem_hash": "regression-v1"}])
def test_incompatible_problem_or_objective_never_aggregates(tmp_path, other):
    from study.report import build_report_data
    write_run(tmp_path, "a", **generic_summary())
    write_run(tmp_path, "b", **other)
    with pytest.raises(ValueError, match="(?i)(incompatible|objective|direction)"):
        build_report_data(tmp_path)


def test_generic_r2_can_be_negative_and_invalid_metric_bounds_are_excluded(tmp_path):
    from study.report import build_report_data
    write_run(tmp_path, "r2", trials=[generic_trial("poor", 1, -7, "r2"),
              generic_trial("better", 2, -.2, "r2"), generic_trial("impossible", 3, 2, "r2")],
              **generic_summary("r2", "maximize", "r2-data", target_definitions=[{"name": "baseline", "value": 0}]))
    row = build_report_data(tmp_path)["runs"][0]
    assert row["best_score"] == -.2
    assert row["targets"]["baseline"]["reached"] is False
    assert row["valid_completed_trials"] == 2


def test_report_preserves_observed_trial_artifact_and_accounting_metadata(tmp_path):
    from study.report import build_report_data
    selected = generic_trial("one", 8, 3.0, artifact="pipeline.joblib", artifact_hash="frozen",
                             accounting={"known_cost": .25, "cost_complete": True})
    write_run(tmp_path, "sparse", trials=[selected],
              **generic_summary(best=selected, target_selections={"usable model": selected}))
    row = build_report_data(tmp_path)["runs"][0]
    assert row["best"]["artifact_hash"] == "frozen"
    assert row["best"]["accounting"]["known_cost"] == .25
    assert row["targets"]["usable model"]["artifact"] == "pipeline.joblib"



@pytest.mark.parametrize("second_fingerprint", ["other-snapshot", None])
def test_report_refuses_different_or_unknown_data_snapshots(tmp_path, second_fingerprint):
    from study.report import build_report_data
    write_run(tmp_path, "a", **generic_summary(data_fingerprint="snapshot-a"))
    write_run(tmp_path, "b", **generic_summary(data_fingerprint=second_fingerprint))
    with pytest.raises(ValueError, match="(?i)(incompatible|fingerprint|snapshot)"):
        build_report_data(tmp_path)


def test_report_same_data_fingerprint_and_unfinished_suite_rows_are_compatible(tmp_path):
    from study.report import build_report_data
    metadata = generic_summary(data_fingerprint="snapshot-a")
    for name in ("done-a", "done-b"):
        write_run(tmp_path, name, **metadata)
    interrupted = tmp_path / "runs" / "interrupted"
    interrupted.mkdir()
    (interrupted / "events.jsonl").write_text("")
    schedule = [{"run_id": name, "condition": "researcher_alone", "repeat": repeat}
                for repeat, name in enumerate(("done-a", "done-b", "interrupted", "unstarted"))]
    (tmp_path / "suite.json").write_text(json.dumps({**metadata,
        "config": {"allowance_seconds": 100, "decision_protocol": "structured_v1"}, "schedule": schedule}))
    data = build_report_data(tmp_path)
    assert len(data["runs"]) == 4
    assert data["data_fingerprint"] == "snapshot-a"
    assert {run["data_fingerprint"] for run in data["runs"]} == {"snapshot-a"}
    assert data["runs"][2]["stop_reason"] == "interrupted_unrecovered"


def test_provider_file_cannot_supply_missing_frozen_run_identity(tmp_path):
    from study.report import build_report_data
    folder = write_run(tmp_path, "unknown", **generic_summary())
    (folder / "provider.json").write_text(json.dumps({"runtime": {
        "data_manifest": {"data_fingerprint": "snapshot-a"}}}))
    write_run(tmp_path, "known", **generic_summary(data_fingerprint="snapshot-a"))
    with pytest.raises(ValueError, match="(?i)(incompatible|snapshot)"):
        build_report_data(tmp_path)


def test_same_npz_path_with_different_prepared_source_bytes_cannot_pool(tmp_path):
    import asyncio
    import numpy as np
    from study.config import StudyConfig
    from study.controller import run_one
    from study.problem import ProblemSpec
    from study.science import prepare_dataset
    from study.report import build_report_data
    source = tmp_path / "source.npz"
    value = {"schema_version": 1, "id": "same-source-path", "task": "tabular_classification",
        "brief": "Predict three classes.", "dataset": {"format": "npz", "path": str(source),
            "feature_array": "X", "target_array": "y"},
        "evaluation": {"split": {"train": .6, "validation": .2, "test": .2},
                       "objective": {"metric": "accuracy", "direction": "maximize"}},
        "targets": [], "search_space": {"preset": "tabular_classification_small", "models": ["logistic"]}}
    problem = ProblemSpec.from_dict(value)
    class Model:
        async def complete(self, messages, tools, *, timeout):
            return {"message": {"role": "assistant", "tool_calls": [{"id": "fit", "type": "function",
                "function": {"name": "run_analysis", "arguments": json.dumps({"model": "logistic",
                    "preprocessing": "standard", "params": {}})}}]},
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0}}
    async def runner(*args, **kwargs):
        return {"status": "completed", "score": .8, "metrics": {"accuracy": .8},
                "artifact": "fake", "artifact_hash": "fake"}
    results = []
    root = tmp_path / "report"
    for seed in (0, 1):
        np.savez(source, X=np.random.default_rng(seed).normal(size=(120, 4)), y=np.tile([0, 1, 2], 40))
        data = tmp_path / f"data-{seed}"
        prepare_dataset(data, problem=problem)
        results.append(asyncio.run(run_one(StudyConfig(trial_cap=1), data, root / "runs" / str(seed),
            Model(), trial_runner=runner)))
    assert results[0]["problem_hash"] == results[1]["problem_hash"]
    assert results[0]["data_fingerprint"] != results[1]["data_fingerprint"]
    with pytest.raises(ValueError, match="(?i)(incompatible|fingerprint|snapshot)"):
        build_report_data(root)


def test_suite_fingerprint_does_not_fill_existing_unknown_run_identity(tmp_path):
    from study.report import build_report_data
    write_run(tmp_path, "old", **generic_summary())
    (tmp_path / "suite.json").write_text(json.dumps({**generic_summary(data_fingerprint="snapshot-a"),
        "config": {"allowance_seconds": 100, "decision_protocol": "structured_v1"}, "schedule": [
            {"run_id": "old", "condition": "researcher_alone", "repeat": 0}]}))
    with pytest.raises(ValueError, match="(?i)(incompatible|fingerprint|snapshot)"):
        build_report_data(tmp_path)


def test_report_rejects_conflicting_independent_run_fingerprints(tmp_path):
    from study.report import build_report_data
    folder = write_run(tmp_path, "conflicting", **generic_summary(data_fingerprint="snapshot-a"))
    (folder / "events.jsonl").write_text(json.dumps({"type": "run_started", "data_fingerprint": "snapshot-b"}) + "\n")
    with pytest.raises(ValueError, match="(?i)(incompatible|fingerprint|snapshot)"):
        build_report_data(tmp_path)
