"""Offline study reports. Unknown outcomes and accounting are never zero-filled."""
from __future__ import annotations

import base64
import csv
import html
import io
import json
import math
import os
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Any

TOKEN_FIELDS = ("input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens")


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _read(path: Path, warnings: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("expected a JSON object")
        return value
    except (OSError, ValueError) as exc:
        warnings.append(f"Could not read {path.name}: {exc}")
        return {}


def _events(folder: Path, warnings: list[str]) -> list[dict]:
    path = folder / "events.jsonl"
    if not path.exists():
        return []
    result = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            if isinstance(event, dict):
                result.append(event)
        except ValueError:
            warnings.append(f"Invalid event line {line_number} in {folder.name}")
    return result


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


def _trials(summary: dict, events: list[dict]) -> list[dict]:
    """Prefer controller-frozen completion time; accept raw evaluator event results."""
    trials = {}
    records = summary.get("trials")
    for index, entry in enumerate(records if isinstance(records, list) else []):
        if not isinstance(entry, dict):
            continue
        item = {**(entry.get("result") or {}), **entry}
        identity = str(item.get("trial_id", item.get("id", index)))
        trials[identity] = {**item, "trial_id": identity}
    for index, event in enumerate(events):
        if event.get("type") != "trial_finished":
            continue
        result = event.get("result") or {}
        identity = str(event.get("trial_id", result.get("trial_id", result.get("id", index))))
        trials[identity] = {**result, "trial_id": identity,
                            "elapsed_seconds": (result.get("elapsed_seconds") if "duration_seconds" in result
                                                else event.get("elapsed_seconds")),
                            "training_seconds": result.get("training_seconds",
                                result.get("duration_seconds", result.get("elapsed_seconds")))}
    # Frozen selections remain usable when detailed trial records are absent.
    for name, item in _selections(summary).items():
        if isinstance(item, dict):
            identity = str(item.get("trial_id", item.get("id", name)))
            trials[identity] = {**item, "status": "completed",
                                **trials.get(identity, {}), "trial_id": identity}
    return list(trials.values())


def _objective(summary: dict) -> dict:
    objective = summary.get("objective") or {"metric": "roc_auc", "direction": "maximize"}
    from .problem import METRICS
    metric = objective.get("metric")
    if metric not in METRICS or objective.get("direction") != METRICS[metric]["direction"]:
        raise ValueError(f"Invalid report objective metric/direction: {objective}")
    return {"metric": metric, "direction": objective["direction"]}


def _score(item: dict, metric: str) -> float | None:
    score = _number(item.get("score"))
    if score is None:
        score = _number((item.get("metrics") or {}).get(metric))
    if score is None and metric == "roc_auc":
        score = _number(item.get("validation_auc"))
    if score is None:
        return None
    from .problem import validate_metric_value
    try:
        validate_metric_value(metric, score)
    except ValueError:
        return None
    return score


def _definitions(summary: dict) -> list[dict]:
    if "target_definitions" in summary:
        return summary["target_definitions"]
    if "objective" in summary:
        return (summary.get("problem") or {}).get("targets", [])
    config = summary.get("config") or {}
    return [{"name": name, "value": config.get(name, config.get(name + "_auc", default))}
            for name, default in (("milestone", .93), ("stretch", .95))]


def _selections(summary: dict) -> dict:
    if "objective" in summary:
        return {**(summary.get("target_selections") or {}), "best": summary.get("best")}
    return {name: summary.get(name) for name in ("best", "milestone", "stretch")}


def _data_fingerprint(summary: dict, folder: Path, events: list[dict], warnings: list[str]):
    """Use this run's own frozen identity, including historical provider provenance."""
    candidates = [summary.get("data_fingerprint")]
    candidates.extend(event.get("data_fingerprint") for event in events
                      if event.get("type") == "run_started")
    for filename in ("resolved-config.json", "provider.json"):
        path = folder / filename
        if path.exists():
            record = _read(path, warnings)
            candidates.append(record.get("data_fingerprint"))
            candidates.append(((record.get("runtime") or {}).get("data_manifest") or {}).get("data_fingerprint"))
    known = {value for value in candidates if value is not None}
    if len(known) > 1:
        raise ValueError("Incompatible data fingerprints in frozen run records; report each data snapshot separately.")
    return next(iter(known), None)


def _run_data(path: Path, warnings: list[str], summary_override=None, shared_test_cache=None) -> dict:
    summary = _read(path, warnings) if summary_override is None else summary_override
    objective = _objective(summary)
    metric, direction = objective["metric"], objective["direction"]
    maximize = direction == "maximize"
    definitions = _definitions(summary)
    selections = _selections(summary)
    events = _events(path.parent, warnings)
    allowance = _number(summary.get("allowance_seconds"))
    trials = _trials(summary, events)
    valid = [{**trial, "score": _score(trial, metric)} for trial in trials
             if trial.get("status") == "completed" and _score(trial, metric) is not None
             and _number(trial.get("elapsed_seconds")) is not None
             and trial["elapsed_seconds"] >= 0
             and allowance is not None and trial["elapsed_seconds"] <= allowance]
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
    tests_path = path.parent / "test-results.json"
    tests = _read(tests_path, warnings) if tests_path.exists() else {}
    tests = tests.get("selections", tests)
    # A shared cache is durable even if per-run views were never written.
    for name, selection in selections.items():
        stored = (shared_test_cache or {}).get((selection or {}).get("artifact_hash"))
        if stored is not None:
            tests[name] = {**stored, "status": "uncertain"} if stored.get("status") == "in_progress" else stored

    def test_result(name):
        result = tests.get(name) or {}
        score = _number(result.get("score"))
        if score is None:
            score = _number((result.get("metrics") or {}).get(metric))
        if score is None and metric == "roc_auc":
            score = _number(result.get("test_auc"))
        status = result.get("status", "completed" if score is not None else "not evaluated")
        return {"test_score": score if status == "completed" else None,
                "test_metrics": result.get("metrics", {}) if status == "completed" else {},
                "test_status": status}

    postrun_path = path.parent / "postrun.json"
    postrun = (_read(postrun_path, warnings) if postrun_path.exists()
               else summary.get("postrun_accounting") or {})
    training = _number(summary.get("training_seconds"))
    measured = [_number(t.get("training_seconds")) for t in trials]
    if training is None and measured and all(t is not None for t in measured):
        training = sum(measured)
    best_test = test_result("best")
    row = {
        "run_id": summary.get("run_id", path.parent.name),
        "condition": str(summary.get("condition", "unknown")),
        "repeat": summary.get("repeat"), "allowance_seconds": allowance,
        "objective": objective, "problem_hash": summary.get("problem_hash"),
        "data_fingerprint": _data_fingerprint(summary, path.parent, events, warnings),
        "problem": summary.get("problem"), "target_definitions": definitions,
        "elapsed_seconds": _number(summary.get("elapsed_seconds")),
        "stop_reason": str(summary.get("stop_reason", "unknown")),
        "trial_attempts": (summary["trials"] if isinstance(summary.get("trials"), int)
                           else len(summary.get("trials") or trials)),
        "valid_completed_trials": len(valid),
        "best_score": best["score"] if best else None,
        "best_metrics": (best.get("metrics") or {metric: best["score"]}) if best else {},
        "best_trial_id": best["trial_id"] if best else None,
        "best": best, "best_curve": curve, "training_seconds": training,
        **{"best_" + key: value for key, value in best_test.items()},
        **_accounting(summary.get("accounting")),
        "evaluation_seconds": _number(postrun.get("evaluation_seconds")),
        "reporting_seconds": _number(postrun.get("reporting_seconds")),
        "postrun_accounting": postrun,
        "event_counts": dict(Counter(e.get("type", "unknown") for e in events)),
        "trace": [e for e in events if e.get("type") in
                  ("review", "reflection", "selection", "run_stopped")],
        "targets": {},
    }
    for definition in definitions:
        name, threshold = definition["name"], _number(definition["value"])
        if threshold is None:
            raise ValueError(f"Invalid report target threshold: {name}")
        crossing = next((item for item in valid if
                         (item["score"] >= threshold if maximize else item["score"] <= threshold)), None)
        selection = selections.get(name) or {}
        details = {key: crossing.get(key) if crossing else None for key in
                   ("trial_id", "score", "metrics", "artifact", "artifact_hash")}
        details.update({"threshold": threshold, "reached": crossing is not None,
                        "seconds": float(crossing["elapsed_seconds"]) if crossing else None,
                        **_accounting(selection.get("accounting") if crossing else None),
                        **test_result(name)})
        row["targets"][name] = details
        if metric == "roc_auc" and name in ("milestone", "stretch"):
            row.update({name + "_auc": threshold, name + "_reached": details["reached"],
                        name + "_seconds": details["seconds"],
                        **_accounting(selection.get("accounting") if crossing else None, name + "_")})
    if metric == "roc_auc":
        row["best_validation_auc"] = row["best_score"]
        for name in ("best", "milestone", "stretch"):
            result = test_result(name)
            row[name + "_test_auc"] = result["test_score"]
            row[name + "_test_status"] = result["test_status"]
    return row


def build_report_data(root: Path) -> dict:
    """Read frozen artifacts offline, retaining every scheduled run in denominators.

    Different problem identities or objectives cannot be pooled in one report.
    """
    root = Path(root)
    warnings: list[str] = []
    cache_path = root / "evaluation" / "test-evaluation-cache.json"
    shared_test_cache = (_read(cache_path, warnings).get("artifacts", {})
                         if cache_path.exists() else {})
    paths = ([root / "summary.json"] if (root / "summary.json").exists() else [])
    if (root / "runs").exists():
        paths.extend(sorted((root / "runs").rglob("summary.json")))
    manifest_path = root / "suite.json"
    manifest = _read(manifest_path, warnings) if manifest_path.exists() else {}
    records = {path: _read(path, warnings) for path in dict.fromkeys(paths)}
    metadata_fields = ("objective", "problem", "problem_hash", "target_definitions", "data_fingerprint")
    metadata = {key: manifest[key] for key in metadata_fields if key in manifest}
    if "objective" not in metadata:
        inferred = next(({key: item[key] for key in metadata_fields if key in item}
                         for item in records.values() if "objective" in item), {})
        metadata = {**inferred, **metadata}
    if "data_fingerprint" not in manifest and manifest_path.exists():
        metadata["data_fingerprint"] = ((manifest.get("provenance") or {}).get("data_manifest") or {}).get("data_fingerprint")
    runs = []
    if manifest_path.exists():
        config = manifest.get("config") or {}
        planned = manifest.get("schedule", [])
        planned_paths = set()
        for entry in planned:
            path = root / "runs" / entry["run_id"] / "summary.json"
            planned_paths.add(path)
            if path in records:
                summary = records[path]
            else:
                interrupted = (path.parent / "events.jsonl").exists()
                warnings.append(f"Incomplete suite: {entry['run_id']} "
                                + ("needs recovery after interruption." if interrupted else "has not started."))
                summary = {**metadata, "run_id": entry["run_id"], "condition": entry["condition"],
                           "repeat": entry["repeat"], "config": config,
                           "allowance_seconds": config.get("allowance_seconds"),
                           "stop_reason": "interrupted_unrecovered" if interrupted else "not_started"}
            runs.append(_run_data(path, warnings, summary, shared_test_cache))
        if set(paths) - planned_paths:
            warnings.append("Unscheduled run directories were excluded from the frozen suite comparison.")
    else:
        runs = [_run_data(path, warnings, summary, shared_test_cache) for path, summary in records.items()]
    identities = {(r["objective"]["metric"], r["objective"]["direction"], r["problem_hash"],
                   json.dumps(r["problem"], sort_keys=True), r["data_fingerprint"]) for r in runs}
    if metadata and manifest_path.exists():
        objective = _objective(metadata)
        identities.add((objective["metric"], objective["direction"], metadata.get("problem_hash"),
                        json.dumps(metadata.get("problem"), sort_keys=True), metadata.get("data_fingerprint")))
    if len(identities) > 1:
        raise ValueError("Incompatible problem identities, objectives, or data fingerprints in report; "
                         "known and unknown data snapshots cannot be pooled. Generate a separate report for each data snapshot.")
    objective = runs[0]["objective"] if runs else _objective(metadata)
    if any(r["stop_reason"].startswith(("not_started", "interrupted")) for r in runs):
        warnings.append("Incomplete comparison: some planned runs did not finish; do not interpret it as a matched study.")
    grouped = defaultdict(list)
    for row in runs:
        grouped[row["condition"]].append(row)
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
            aggregate["targets"][name] = {"fraction": len(times) / len(rows), "curve": points}
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
    postrun_path = root / "postrun.json"
    postrun = _read(postrun_path, warnings) if postrun_path.exists() else {}
    first = runs[0] if runs else metadata
    return {"runs": runs, "conditions": conditions, "warnings": warnings, "objective": objective,
            "problem_hash": first.get("problem_hash"), "problem": first.get("problem"),
            "data_fingerprint": first.get("data_fingerprint"),
            "postrun_accounting": postrun}

def _display(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.6g}"
    return html.escape(str(value))


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    return ("<table><thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers)
            + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{_display(v)}</td>" for v in r)
                                                       + "</tr>" for r in rows) + "</tbody></table>")


def _plots(data: dict) -> str:
    # Headless reports must also work in restricted, non-writable home folders.
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "nightagent-matplotlib"))
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    figure = Figure(figsize=(12, 10), layout="constrained")
    FigureCanvasAgg(figure)
    progress, attainment, cost, tokens = figure.subplots(2, 2).flat
    palette = ["#2563eb", "#d97706", "#059669", "#9333ea", "#dc2626"]
    colors = {name: palette[i % len(palette)] for i, name in enumerate(data["conditions"])}
    labels_seen = set()
    metric = data["objective"]["metric"]
    metric_label = {"roc_auc": "ROC-AUC", "roc_auc_ovr_macro": "ROC-AUC (macro one-vs-rest)"}.get(metric, metric)
    for row in data["runs"]:
        name = row["condition"]
        curve = row["best_curve"]
        label = name if name not in labels_seen else None
        if curve:
            x, y = zip(*curve)
            progress.step(x, y, where="post", color=colors[name], alpha=.7, label=label)
            labels_seen.add(name)
        auc = row["best_score"]
        if auc is not None and row["known_cost"] is not None:
            cost.scatter(row["known_cost"], auc, color=colors[name],
                         marker="o" if row["cost_complete"] else "x")
        if auc is not None and row["input_tokens"] is not None and row["output_tokens"] is not None:
            tokens.scatter(row["input_tokens"] + row["output_tokens"], auc, color=colors[name],
                           marker="o" if row["token_usage_complete"] else "x")
    deadlines = sorted({r["allowance_seconds"] for r in data["runs"] if r["allowance_seconds"] is not None})
    for deadline in deadlines:
        progress.axvline(deadline, color="#64748b", linestyle=":", alpha=.7)
        attainment.axvline(deadline, color="#64748b", linestyle=":", alpha=.7)
    target_names = list(dict.fromkeys(name for row in data["runs"] for name in row["targets"]))
    for name in target_names:
        thresholds = {r["targets"][name]["threshold"] for r in data["runs"] if name in r["targets"]}
        for threshold in sorted(thresholds):
            progress.axhline(threshold, color="#94a3b8", linestyle="--", linewidth=.7)
            progress.text(.02, threshold, f" {name} {threshold:g}", fontsize=8,
                          transform=progress.get_yaxis_transform(), va="bottom")
    styles = ("-", "--", "-.", ":")
    for name, aggregate in data["conditions"].items():
        for index, (target, details) in enumerate(aggregate["targets"].items()):
            x, y = zip(*details["curve"])
            attainment.step(x, y, where="post", color=colors[name], linestyle=styles[index % len(styles)],
                            label=f"{name}: {target}")
    progress.set(title=f"Best completed validation {metric_label} (each run)", xlabel="Elapsed seconds",
                 ylabel=f"Validation {metric_label} ({data['objective']['direction']})",
                 xlim=(0, max(deadlines) * 1.03 if deadlines else 1))
    attainment.set(title="Target attainment / all runs", xlabel="Elapsed seconds", ylabel="Fraction of all runs", ylim=(-.02, 1.02))
    cost.set(title="API cost through stopping (× = incomplete lower bound)", xlabel="Known API cost, USD", ylabel=f"Deadline validation {metric_label}")
    tokens.set(title="Tokens through stopping (× = incomplete subtotal)", xlabel="Input + output tokens", ylabel=f"Deadline validation {metric_label}")
    for axes in (progress, attainment, cost, tokens):
        axes.grid(alpha=.15)
    if labels_seen:
        progress.legend(fontsize=7)
    if any(a["targets"] for a in data["conditions"].values()):
        attainment.legend(fontsize=6)
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=130)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f'<img alt="Validation progress, all-run attainment, API cost and tokens" src="data:image/png;base64,{encoded}">'


def generate_report(root: Path) -> Path:
    """Write a portable CSV and self-contained HTML report; make no API calls."""
    started = time.perf_counter()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    data = build_report_data(root)
    runs = data["runs"]
    fields = [key for row in runs for key in row if key not in
              ("best_curve", "postrun_accounting", "event_counts", "trace")]
    fields = list(dict.fromkeys(fields)) or ["run_id", "condition", "best_validation_auc"]
    with (root / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({key: json.dumps(value, sort_keys=True, ensure_ascii=False)
                          if isinstance(value, (dict, list)) else value
                          for key, value in row.items()} for row in runs)
    objective = data["objective"]
    metric = {"roc_auc": "ROC-AUC", "roc_auc_ovr_macro": "ROC-AUC (macro one-vs-rest)"}.get(objective["metric"], objective["metric"])
    target_names = list(dict.fromkeys(name for row in runs for name in row["targets"]))
    sections = ["<h1>Overnight study: validation performance at the deadline</h1>",
                f"<p>Primary outcome: best completed validation {html.escape(metric)} "
                f"({html.escape(objective['direction'])}) within each run's scheduled allowance. "
                "Every scheduled run is listed, including failures and runs with no valid model. "
                "Held-out test results are separate generalization checks.</p>"]
    if data["problem_hash"] is not None:
        sections.append("<p>Frozen problem hash: " + _display(data["problem_hash"]) + "</p>")
        sections.append("<details><summary>Frozen problem definition</summary><pre>"
                        + html.escape(json.dumps(data["problem"], indent=2, ensure_ascii=False)) + "</pre></details>")
    if data["data_fingerprint"] is not None:
        sections.append("<p>Frozen prepared data fingerprint: " + _display(data["data_fingerprint"]) + "</p>")
    if objective["metric"] in ("roc_auc", "roc_auc_ovr_macro"):
        sections.append("<p>ROC-AUC measures ranking, not classification accuracy.</p>")
    sections.append(_table(["Condition", "All runs", "Valid models", f"Mean validation {metric} (valid n)",
                            "SD (valid n)"] + [f"{name} fraction (all runs)" for name in target_names],
                           [[name, a["run_count"], a["valid_run_count"], a["best_score_mean"], a["best_score_sd"]]
                            + [a["targets"].get(target, {}).get("fraction") for target in target_names]
                            for name, a in data["conditions"].items()]))
    sections.append("<p>Means and SD describe available model outcomes with valid n shown; "
                    "they do not impute a score to runs without a valid model. Small samples are exploratory. "
                    "Nonattainers have unknown crossing time, never the deadline as their crossing time. "
                    "Early stops carry their last completed score to the scheduled deadline; no uncompleted work is credited. "
                    "Dotted vertical lines mark allowances; dashed horizontal lines mark frozen targets.</p>")
    sections.append(_plots(data) if runs else "<p>No run summaries found.</p>")
    sections.append("<h2>Every run: primary outcome and stop reason</h2>")
    sections.append(_table(["Run", "Condition", "Repeat", "Allowance (s)", "Actual stop (s)", "Stop reason",
                            f"Best validation {metric}", "Attempts"],
                           [[r[k] for k in ("run_id", "condition", "repeat", "allowance_seconds", "elapsed_seconds",
                                            "stop_reason", "best_score", "trial_attempts")] for r in runs]))
    sections.append("<h2>Named validation target crossings</h2>")
    sections.append(_table(["Run", "Target", f"Threshold ({metric})", "Reached", "First crossing (s)"],
                           [[r["run_id"], name, t["threshold"], t["reached"], t["seconds"]]
                            for r in runs for name, t in r["targets"].items()]))
    sections.append("<h2>Held-out test confirmation (post-search)</h2>")
    sections.append(_table(["Run", "Selection", f"Held-out {metric}", "Test status", "Test metrics"],
                           [[r["run_id"], "best", r["best_test_score"], r["best_test_status"],
                             json.dumps(r["best_test_metrics"], sort_keys=True)] for r in runs]
                           + [[r["run_id"], name, t["test_score"], t["test_status"], json.dumps(t["test_metrics"], sort_keys=True)]
                              for r in runs for name, t in r["targets"].items()]))
    sections.append("<h2>API accounting through stopping</h2><p>Dollar totals cover reported model-provider charges "
                    "for all roles, including failed calls, reviews and reflection where recorded. Unknown billing is preserved: "
                    "known cost is only a subtotal when incomplete. Training/tool compute and post-run work are recorded separately; "
                    "their monetary cost is unknown unless explicitly metered. Cached tokens are a subset of input; reasoning tokens "
                    "are a subset of output, so neither is added again. Incomplete token subtotals are not complete totals.</p>")
    sections.append(_table(["Run", "Known USD", "Complete USD total", "Input tokens", "Output tokens", "Cached tokens",
                            "Reasoning tokens", "Complete token total", "Usage complete"],
                           [[r[k] for k in ("run_id", "known_cost", "total_cost", "input_tokens", "output_tokens", "cached_tokens",
                                            "reasoning_tokens", "total_tokens", "token_usage_complete")] for r in runs]))
    sections.append("<h3>Accounting at first target attainment</h3>")
    sections.append(_table(["Run", "Target", "Reached", "Time (s)", "Known USD", "Complete USD", "Complete tokens"],
                           [[r["run_id"], name, t["reached"], t["seconds"], t["known_cost"], t["total_cost"], t["total_tokens"]]
                            for r in runs for name, t in r["targets"].items()]))
    sections.append("<h2>Training/tool compute</h2><p>Trial-process elapsed seconds include preprocessing, fitting and scoring, "
                    "and failed or timed-out attempts where measured. This is wall time, not CPU-seconds or a billed dollar estimate. "
                    "Additional tool compute is unknown unless present in the run's accounting record.</p>")
    sections.append(_table(["Run", "Training/trial elapsed (s)", "Event counts"],
                           [[r["run_id"], r["training_seconds"], json.dumps(r["event_counts"], sort_keys=True)] for r in runs]))
    sections.append("<h2>Post-run evaluation/reporting</h2><p>These measurements are outside search allowances and model-provider "
                    "totals. Missing fields mean unknown. This report's generation time is recorded in report-accounting.json.</p>")
    sections.append("<p>Suite-level post-search accounting (not added to API search totals):</p><pre>"
                    + html.escape(json.dumps(data["postrun_accounting"], indent=2, sort_keys=True)) + "</pre>")
    sections.append(_table(["Run", "Evaluation (s)", "Reporting (s)", "Other post-run accounting"],
                           [[r["run_id"], r["evaluation_seconds"], r["reporting_seconds"],
                             json.dumps(r["postrun_accounting"], sort_keys=True)] for r in runs]))
    sections.append("<h2>Qualitative review and reflection traces</h2><p>These traces explain decisions; "
                    "they do not replace quantitative comparisons.</p>")
    for row in runs:
        sections.append(f'<details><summary>{_display(row["run_id"])}</summary><pre>'
                        + html.escape(json.dumps(row["trace"], indent=2, ensure_ascii=False)) + "</pre></details>")
    if data["warnings"]:
        sections.append("<h2>Data quality notes</h2><ul>" + "".join(f"<li>{html.escape(w)}</li>" for w in data["warnings"]) + "</ul>")
    document = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
                '<title>Overnight study report</title><style>body{font:15px system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#172033}'
                'table{border-collapse:collapse;display:block;overflow-x:auto;margin:1rem 0;width:100%}th,td{padding:.55rem;border:1px solid #cbd5e1;text-align:left}'
                'th{background:#f1f5f9}img{max-width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}p{line-height:1.6}</style>'
                '<body>' + "\n".join(sections) + '</body></html>')
    output = root / "report.html"
    output.write_text(document, encoding="utf-8")
    (root / "report-accounting.json").write_text(json.dumps({
        "reporting_seconds": time.perf_counter() - started,
        "api_calls": 0, "known_api_cost": 0, "training_compute_cost": None,
        "reporting_compute_cost": None,
    }, indent=2), encoding="utf-8")
    return output
