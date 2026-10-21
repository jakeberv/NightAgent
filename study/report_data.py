"""Aggregate loaded study evidence, preserving unknown measurements and denominators."""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Any

from .report_analysis import (assign_analysis_groups, paired_comparisons,
                              recommendation_uptake, role_metrics, literature_coverage)
from .report_efficiency import resource_trajectories, research_efficiency
from .report_loading import RunArtifacts, load_report, selections, trials_from_events

TOKEN_FIELDS = ("input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens")


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _accounting(account: dict | None, prefix: str = "") -> dict:
    account = account or {}
    known_cost = _number(account.get("known_cost"))
    complete = account.get("cost_complete") is True
    tokens_complete = account.get("token_usage_complete") is True
    values = {key: (_number(account.get(key)) if account.get(key + "_complete") is not False
                    else None) for key in TOKEN_FIELDS}
    # Cached and reasoning tokens are subsets of input/output, not extra tokens.
    total_tokens = (values["input_tokens"] + values["output_tokens"]
                    if tokens_complete and values["input_tokens"] is not None
                    and values["output_tokens"] is not None else None)
    return {prefix + key: value for key, value in {
        "known_cost": known_cost, "cost_complete": complete,
        "total_cost": known_cost if complete else None,
        "token_usage_complete": tokens_complete, "total_tokens": total_tokens,
        **values,
    }.items()}


def _objective(summary: dict) -> dict:
    objective = summary.get("objective")
    if not isinstance(objective, dict):
        raise ValueError("Report requires a frozen objective metric/direction")
    from .problem import METRICS
    metric = objective.get("metric")
    if metric not in METRICS or objective.get("direction") != METRICS[metric]["direction"]:
        raise ValueError(f"Invalid report objective metric/direction: {objective}")
    return {"metric": metric, "direction": objective["direction"]}


def _score(item: dict, metric: str) -> float | None:
    score = _number(item.get("score"))
    if score is None:
        score = _number((item.get("metrics") or {}).get(metric))
    if score is None:
        return None
    from .problem import validate_metric_value
    try:
        validate_metric_value(metric, score)
    except ValueError:
        return None
    return score


def _valid_score(trial, metric, allowance):
    """One observed result's eligible score, shared by outcomes and trajectories."""
    elapsed = _number(trial.get('elapsed_seconds'))
    if (trial.get('status') != 'completed' or elapsed is None or elapsed < 0
            or allowance is None or elapsed > allowance):
        return None
    return _score(trial, metric)


def _budget(value):
    value = _number(value)
    return value if value is not None and value >= 0 else None


def _budget_summary(values):
    known = [number for value in values if (number := _budget(value)) is not None]
    return {'n': len(known), 'missing': len(values) - len(known),
            'mean': mean(known) if known else None,
            'sd': stdev(known) if len(known) > 1 else None,
            'min': min(known) if known else None, 'max': max(known) if known else None}


def _target_efficiency(rows, name):
    """Observed first-attainment budgets, without success-only denominators or extrapolation."""
    reached = [row for row in rows if row['targets'].get(name, {}).get('reached')]
    missed = [row for row in rows if not row['targets'].get(name, {}).get('reached')]
    axes = ('seconds', 'total_cost', 'total_tokens')
    endings = [{'run_id': row['run_id'], 'stop_reason': row['stop_reason'],
                'seconds': _budget(row['elapsed_seconds']),
                **{field: row[field] for field in ('known_cost', 'cost_complete', 'total_cost',
                                                  'total_tokens', 'token_usage_complete')}} for row in missed]
    curves = {}
    for field in axes:
        crossings = [_budget(row['targets'][name].get(field)) for row in reached]
        known = [value for value in crossings if value is not None]
        censored = [{'run_id': row['run_id'], 'budget': _budget(row[field])}
                    for row in endings if _budget(row[field]) is not None]
        points = [(0., sum(value == 0 for value in known) / len(rows))]
        for budget in sorted(set(known) - {0.}):
            points.append((budget, sum(value <= budget for value in known) / len(rows)))
        endpoint = max([*known, *(row['budget'] for row in censored)], default=0.)
        if endpoint > points[-1][0]:
            points.append((endpoint, len(known) / len(rows)))
        curves[field] = {'denominator': len(rows), 'known_crossings': len(known), 'curve': points,
            'reached_with_unknown_budget': [row['run_id'] for row, value in zip(reached, crossings) if value is None],
            'not_reached_with_unknown_end_budget': [row['run_id'] for row in endings if _budget(row[field]) is None],
            'censored': censored}
    return {'n': len(rows), 'reached': len(reached), 'not_reached': len(missed),
            'conditional_at_attainment': {field: _budget_summary([row['targets'][name].get(field) for row in reached])
                                         for field in axes},
            'nonattainment': {'n': len(missed), 'observed_end_budgets': endings},
            'attainment_by_budget': curves}


def aggregate_run(artifacts: RunArtifacts, warnings: list[str]) -> dict:
    summary, events = artifacts.summary, artifacts.events
    objective = _objective(summary)
    metric, direction = objective["metric"], objective["direction"]
    maximize = direction == "maximize"
    definitions = summary.get("target_definitions")
    if not isinstance(definitions, list):
        raise ValueError("Report requires frozen target_definitions as a list")
    selected_results = selections(summary)
    allowance = _number(summary.get("allowance_seconds"))
    trials = trials_from_events(events, selected_results)
    valid = [{**trial, "score": score} for trial in trials
             if (score := _valid_score(trial, metric, allowance)) is not None]
    valid.sort(key=lambda trial: trial["elapsed_seconds"])
    best = (max if maximize else min)(valid, key=lambda trial: trial["score"], default=None)
    curve = []
    running = -math.inf if maximize else math.inf
    for item in valid:
        if (item["score"] > running if maximize else item["score"] < running):
            running = item["score"]
            curve.append((float(item["elapsed_seconds"]), running))
    if curve and curve[-1][0] < allowance:
        curve.append((allowance, curve[-1][1]))
    tests = artifacts.tests

    def test_result(name, observed):
        result = tests.get(name) or {}
        digest = (observed or {}).get('artifact_hash')
        if result and (not digest or result.get('artifact_hash') != digest):
            warnings.append(f"Held-out {name} result in {artifacts.folder} does not match "
                            "an observed selected artifact; test outcome remains unknown.")
            return {'test_score': None, 'test_metrics': {}, 'test_status': 'unknown'}
        score = _number(result.get("score"))
        if score is None:
            score = _number((result.get("metrics") or {}).get(metric))
        status = result.get("status", "completed" if score is not None else "not evaluated")
        return {"test_score": score if status == "completed" else None,
                "test_metrics": result.get("metrics", {}) if status == "completed" else {},
                "test_status": status}

    postrun = artifacts.postrun
    training = _number(summary.get("training_seconds"))
    measured = [_number(t.get("training_seconds")) for t in trials]
    if training is None and measured and all(t is not None for t in measured):
        training = sum(measured)
    attempts = summary.get("trials", max(len(trials), sum(event["type"] == "trial_started" for event in events)))
    if type(attempts) is not int or attempts < 0:
        raise ValueError("Report requires a nonnegative integer trial attempt count")
    outcomes = dict.fromkeys(("Completed", "Failed", "Timed out", "Late", "Other / unknown"), 0)
    valid_ids = {t["trial_id"] for t in valid}
    for item in trials:
        status = item.get("status")
        late = (status == "late" or status == "completed" and allowance is not None
                and _number(item.get("elapsed_seconds")) is not None and item["elapsed_seconds"] > allowance)
        label = ("Completed" if item["trial_id"] in valid_ids else "Late" if late else
                 {"failed": "Failed", "timeout": "Timed out"}.get(status, "Other / unknown"))
        outcomes[label] += 1
    outcomes["Other / unknown"] += max(0, attempts - len(trials))
    calls = [e for e in events if e.get("type") == "model_call"]
    model_durations = [_number(e.get("duration_seconds")) for e in calls]
    queue_durations = [_number(t.get("queue_seconds")) for t in trials]
    def measured_total(values):
        known = [value for value in values if value is not None and value >= 0]
        return sum(known) if known else None
    best_test = test_result("best", best)
    row = {
        "run_id": summary.get("run_id", artifacts.folder.name),
        "condition": str(summary.get("condition", "unknown")),
        "config": summary.get("config") or {},
        "decision_protocol": (summary.get("config") or {}).get("decision_protocol"),
        "lesson_memory": (summary.get("config") or {}).get("lesson_memory"),
        "repeat": summary.get("repeat"), "allowance_seconds": allowance,
        "objective": objective, "problem_hash": summary.get("problem_hash"),
        "data_fingerprint": artifacts.data_fingerprint,
        "problem": summary.get("problem"), "target_definitions": definitions,
        "elapsed_seconds": _number(summary.get("elapsed_seconds")),
        "stop_reason": str(summary.get("stop_reason", "unknown")),
        "trial_attempts": attempts, "trial_outcomes": outcomes,
        "model_seconds": measured_total(model_durations),
        "model_seconds_complete": bool(calls) and all(v is not None and v >= 0 for v in model_durations)
            and len(calls) == sum(e.get("type") == "model_call_started" for e in events),
        "queue_seconds": measured_total(queue_durations),
        "queue_seconds_complete": bool(trials) and len(trials) == attempts
            and all(v is not None and v >= 0 for v in queue_durations),
        "valid_completed_trials": len(valid),
        "best_score": best["score"] if best else None,
        "best_metrics": (best.get("metrics") or {metric: best["score"]}) if best else {},
        "best_trial_id": best["trial_id"] if best else None,
        "best": best, "best_curve": curve, "training_seconds": training,
        "training_seconds_complete": training is not None and len(trials) == attempts
            and all(value is not None and value >= 0 for value in measured),
        **{"best_" + key: value for key, value in best_test.items()},
        **_accounting(summary.get("accounting")),
        "evaluation_seconds": _number(postrun.get("evaluation_seconds")),
        "reporting_seconds": _number(postrun.get("reporting_seconds")),
        "postrun_accounting": postrun,
        "event_counts": dict(Counter(e.get("type", "unknown") for e in events)),
        "role_metrics": role_metrics(events),
        "literature_coverage": literature_coverage(events, summary.get("config"), summary.get("condition"),
            events_available=artifacts.events_available),
        "recommendation_uptake": recommendation_uptake(events, trials, valid),
        "trace": [e for e in events if e.get("type") in
                  ("framing", "review", "reflection", "selection", "run_stopped", "decision_contract",
                   "experiment_diagnostic", "experiment_reused", "repeated_tool_call", "lesson_memory")],
        "targets": {},
    }
    for definition in definitions:
        name, threshold = definition["name"], _number(definition["value"])
        if threshold is None:
            raise ValueError(f"Invalid report target threshold: {name}")
        crossing = next((item for item in valid if
                         (item["score"] >= threshold if maximize else item["score"] <= threshold)), None)
        selection = selected_results.get(name) or {}
        crossing_account = crossing.get('accounting') if crossing else None
        if (crossing and crossing_account is None
                and str(selection.get('trial_id')) == str(crossing['trial_id'])):
            crossing_account = selection.get('accounting')
        details = {key: crossing.get(key) if crossing else None for key in
                   ("trial_id", "score", "metrics", "artifact", "artifact_hash")}
        details.update({"threshold": threshold, "reached": crossing is not None,
                        "seconds": float(crossing["elapsed_seconds"]) if crossing else None,
                        **_accounting(crossing_account),
                        **test_result(name, crossing)})
        row["targets"][name] = details
        if metric == "roc_auc" and name in ("milestone", "stretch"):
            row.update({name + "_auc": threshold, name + "_reached": details["reached"],
                        name + "_seconds": details["seconds"],
                        **_accounting(crossing_account, name + "_")})
    if metric == "roc_auc":
        row["best_validation_auc"] = row["best_score"]
        for name in ("best", "milestone", "stretch"):
            result = best_test if name == 'best' else row['targets'].get(name, {
                'test_score': None, 'test_status': 'not evaluated'})
            row[name + "_test_auc"] = result["test_score"]
            row[name + "_test_status"] = result["test_status"]
    row["resource_trajectories"] = resource_trajectories(artifacts, lambda trial: _valid_score(trial, metric, allowance), row)
    return row


def build_report_data(root: Path) -> dict:
    """Read frozen artifacts offline, retaining every scheduled run in denominators."""
    artifacts = load_report(Path(root))
    metadata, warnings = artifacts.metadata, artifacts.warnings
    runs = [aggregate_run(run, warnings) for run in artifacts.runs]
    identities = {(r["objective"]["metric"], r["objective"]["direction"], r["problem_hash"],
                   json.dumps(r["problem"], sort_keys=True), r["data_fingerprint"]) for r in runs}
    if metadata and artifacts.is_suite:
        objective = _objective(metadata)
        identities.add((objective["metric"], objective["direction"], metadata.get("problem_hash"),
                        json.dumps(metadata.get("problem"), sort_keys=True), metadata.get("data_fingerprint")))
    if len(identities) > 1:
        raise ValueError("Incompatible problem identities, objectives, or data fingerprints in report; "
                         "known and unknown data snapshots cannot be pooled. Generate a separate report for each data snapshot.")
    objective = runs[0]["objective"] if runs else _objective(metadata)
    if any(r["stop_reason"].startswith(("not_started", "interrupted")) for r in runs):
        warnings.append("Incomplete comparison: some planned runs did not finish; do not interpret it as a matched study.")
    assign_analysis_groups(runs)
    comparisons = paired_comparisons(runs, warnings)
    grouped = defaultdict(list)
    for row in runs:
        grouped[row["analysis_group"]].append(row)
    conditions = {}
    for condition, rows in grouped.items():
        values = [r["best_score"] for r in rows if r["best_score"] is not None]
        aggregate = {"run_count": len(rows), "valid_run_count": len(values),
                     "best_score_mean": mean(values) if values else None,
                     "best_score_sd": stdev(values) if len(values) > 1 else None,
                     "stop_reasons": dict(Counter(r["stop_reason"] for r in rows)), "targets": {}}
        if objective["metric"] == "roc_auc":
            aggregate.update(best_validation_mean=aggregate["best_score_mean"],
                             best_validation_sd=aggregate["best_score_sd"])
        deadlines = [r["allowance_seconds"] for r in rows if r["allowance_seconds"] is not None]
        for name in dict.fromkeys(name for row in rows for name in row["targets"]):
            times = sorted(r["targets"][name]["seconds"] for r in rows
                           if r["targets"].get(name, {}).get("reached"))
            points = [(0., 0.)]
            for seconds in sorted(set(times)):
                points.append((seconds, sum(t <= seconds for t in times) / len(rows)))
            if deadlines and points[-1][0] < max(deadlines):
                points.append((max(deadlines), len(times) / len(rows)))
            aggregate["targets"][name] = {"fraction": len(times) / len(rows), "curve": points,
                                          **_target_efficiency(rows, name)}
            if objective["metric"] == "roc_auc" and name in ("milestone", "stretch"):
                aggregate[name + "_fraction"] = len(times) / len(rows)
                aggregate[name + "_curve"] = points
        conditions[condition] = aggregate
    allowances = {r["allowance_seconds"] for r in runs if r["allowance_seconds"] is not None}
    if len(allowances) > 1:
        warnings.append("Run allowances differ: this is not an equal-wall-time comparison.")
    for name in dict.fromkeys(name for row in runs for name in row["targets"]):
        thresholds = {r["targets"].get(name, {}).get("threshold") for r in runs}
        if len(thresholds) > 1:
            warnings.append(f"{name} thresholds differ or are missing between runs; compare with care.")
    first = runs[0] if runs else metadata
    return {"research_efficiency": research_efficiency(runs, objective),
            "provenance": artifacts.provenance,
            "runs": runs, "conditions": conditions, "paired_comparisons": comparisons,
            "warnings": warnings, "objective": objective,
            "problem_hash": first.get("problem_hash"), "problem": first.get("problem"),
            "data_fingerprint": first.get("data_fingerprint"),
            "postrun_accounting": artifacts.postrun}
