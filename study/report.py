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
                            "training_seconds": result.get("duration_seconds", result.get("elapsed_seconds"))}
    # Frozen selections remain usable when detailed trial records are absent.
    for name in ("best", "milestone", "stretch"):
        item = summary.get(name)
        if isinstance(item, dict):
            identity = str(item.get("trial_id", item.get("id", name)))
            trials.setdefault(identity, {**item, "trial_id": identity, "status": "completed"})
    return list(trials.values())


def _run_data(path: Path, warnings: list[str], summary_override=None, shared_test_cache=None) -> dict:
    summary = _read(path, warnings) if summary_override is None else summary_override
    events = _events(path.parent, warnings)
    allowance = _number(summary.get("allowance_seconds"))
    config = summary.get("config") or {}
    milestone = _number(config.get("milestone", config.get("milestone_auc")))
    stretch = _number(config.get("stretch", config.get("stretch_auc")))
    milestone = .93 if milestone is None else milestone
    stretch = .95 if stretch is None else stretch
    trials = _trials(summary, events)
    valid = [trial for trial in trials
             if trial.get("status") == "completed"
             and _number(trial.get("validation_auc")) is not None
             and 0 <= trial["validation_auc"] <= 1
             and _number(trial.get("elapsed_seconds")) is not None
             and trial["elapsed_seconds"] >= 0
             and allowance is not None and trial["elapsed_seconds"] <= allowance]
    valid.sort(key=lambda trial: trial["elapsed_seconds"])
    best = max(valid, key=lambda trial: trial["validation_auc"], default=None)
    curve = []
    running = -math.inf
    for item in valid:
        if item["validation_auc"] > running:
            running = item["validation_auc"]
            curve.append((float(item["elapsed_seconds"]), float(running)))
    if curve and curve[-1][0] < allowance:
        curve.append((allowance, curve[-1][1]))
    tests_path = path.parent / "test-results.json"
    tests = _read(tests_path, warnings) if tests_path.exists() else {}
    tests = tests.get("selections", tests)
    # Evaluation persists each score before projecting per-run views. If killed
    # midway, retain completed scores directly from the shared durable cache.
    for name in ("best", "milestone", "stretch"):
        digest = (summary.get(name) or {}).get("artifact_hash")
        stored = (shared_test_cache or {}).get(digest)
        if stored is not None:
            tests[name] = {**stored, "status": "uncertain"} if stored.get("status") == "in_progress" else stored
    postrun_path = path.parent / "postrun.json"
    postrun = (_read(postrun_path, warnings) if postrun_path.exists()
               else summary.get("postrun_accounting") or {})
    training = _number(summary.get("training_seconds"))
    measured = [_number(t.get("training_seconds")) for t in trials]
    if training is None and measured and all(t is not None for t in measured):
        training = sum(measured)
    row = {
        "run_id": summary.get("run_id", path.parent.name),
        "condition": str(summary.get("condition", "unknown")),
        "repeat": summary.get("repeat"), "allowance_seconds": allowance,
        "elapsed_seconds": _number(summary.get("elapsed_seconds")),
        "stop_reason": str(summary.get("stop_reason", "unknown")),
        "trial_attempts": (summary["trials"] if isinstance(summary.get("trials"), int)
                           else len(summary.get("trials") or trials)),
        "valid_completed_trials": len(valid),
        "best_validation_auc": best["validation_auc"] if best else None,
        "best_trial_id": best["trial_id"] if best else None,
        "best_curve": curve, "training_seconds": training,
        **_accounting(summary.get("accounting")),
        "evaluation_seconds": _number(postrun.get("evaluation_seconds")),
        "reporting_seconds": _number(postrun.get("reporting_seconds")),
        "postrun_accounting": postrun,
        "event_counts": dict(Counter(e.get("type", "unknown") for e in events)),
        "trace": [e for e in events if e.get("type") in
                  ("review", "reflection", "selection", "run_stopped")],
    }
    for name, threshold in (("milestone", milestone), ("stretch", stretch)):
        crossing = next((item for item in valid if item["validation_auc"] >= threshold), None)
        selection = summary.get(name) or {}
        row.update({name + "_auc": threshold, name + "_reached": crossing is not None,
                    name + "_seconds": float(crossing["elapsed_seconds"]) if crossing else None,
                    **_accounting(selection.get("accounting") if crossing else None, name + "_")})
    for name in ("best", "milestone", "stretch"):
        result = tests.get(name) or {}
        auc = _number(result.get("test_auc"))
        row[name + "_test_auc"] = auc if result.get("status", "completed") == "completed" else None
        row[name + "_test_status"] = result.get("status", "completed" if auc is not None else "not evaluated")
    return row


def build_report_data(root: Path) -> dict:
    """Read frozen run artifacts, without evaluating models or accessing test data.

    Every discovered run remains in attainment denominators. Means of available
    validation outcomes include their explicit valid count; missing classifiers
    are never replaced with zero or silently removed from the all-run table.
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
    if manifest_path.exists():
        manifest = _read(manifest_path, warnings)
        planned = manifest.get("schedule", [])
        runs = []
        config = manifest.get("config") or {}
        for entry in planned:
            path = root / "runs" / entry["run_id"] / "summary.json"
            if path.exists():
                runs.append(_run_data(path, warnings, shared_test_cache=shared_test_cache))
            else:
                interrupted = (path.parent / "events.jsonl").exists()
                warnings.append(f"Incomplete suite: {entry['run_id']} "
                                + ("needs recovery after interruption." if interrupted else "has not started."))
                runs.append(_run_data(path, warnings, {
                    "run_id": entry["run_id"], "condition": entry["condition"],
                    "repeat": entry["repeat"], "config": config,
                    "allowance_seconds": config.get("allowance_seconds"),
                    "stop_reason": "interrupted_unrecovered" if interrupted else "not_started",
                }, shared_test_cache=shared_test_cache))
        planned_paths = {root / "runs" / entry["run_id"] / "summary.json" for entry in planned}
        if set(paths) - planned_paths:
            warnings.append("Unscheduled run directories were excluded from the frozen suite comparison.")
    else:
        runs = [_run_data(path, warnings, shared_test_cache=shared_test_cache) for path in dict.fromkeys(paths)]
    if any(r["stop_reason"].startswith(("not_started", "interrupted")) for r in runs):
        warnings.append("Incomplete comparison: some planned runs did not finish; do not interpret it as a matched study.")
    grouped = defaultdict(list)
    for row in runs:
        grouped[row["condition"]].append(row)
    conditions = {}
    for condition, rows in grouped.items():
        values = [r["best_validation_auc"] for r in rows if r["best_validation_auc"] is not None]
        aggregate = {"run_count": len(rows), "valid_run_count": len(values),
                     "best_validation_mean": mean(values) if values else None,
                     "best_validation_sd": stdev(values) if len(values) > 1 else None,
                     "stop_reasons": dict(Counter(r["stop_reason"] for r in rows))}
        deadlines = [r["allowance_seconds"] for r in rows if r["allowance_seconds"] is not None]
        for name in ("milestone", "stretch"):
            times = sorted(r[name + "_seconds"] for r in rows if r[name + "_reached"])
            points = [(0., 0.)]
            for seconds in sorted(set(times)):
                points.append((seconds, sum(t <= seconds for t in times) / len(rows)))
            if deadlines and points[-1][0] < max(deadlines):
                points.append((max(deadlines), len(times) / len(rows)))
            aggregate[name + "_fraction"] = len(times) / len(rows)
            aggregate[name + "_curve"] = points
        conditions[condition] = aggregate
    allowances = sorted({r["allowance_seconds"] for r in runs if r["allowance_seconds"] is not None})
    if len(allowances) > 1:
        warnings.append("Run allowances differ: this is not an equal-wall-time comparison.")
    for name in ("milestone", "stretch"):
        if len({r[name + "_auc"] for r in runs}) > 1:
            warnings.append(f"{name.title()} thresholds differ between runs; compare with care.")
    postrun_path = root / "postrun.json"
    postrun = _read(postrun_path, warnings) if postrun_path.exists() else {}
    return {"runs": runs, "conditions": conditions, "warnings": warnings,
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
    for row in data["runs"]:
        name = row["condition"]
        curve = row["best_curve"]
        label = name if name not in labels_seen else None
        if curve:
            x, y = zip(*curve)
            progress.step(x, y, where="post", color=colors[name], alpha=.7, label=label)
            labels_seen.add(name)
        auc = row["best_validation_auc"]
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
    for name in ("milestone", "stretch"):
        for threshold in sorted({r[name + "_auc"] for r in data["runs"]}):
            progress.axhline(threshold, color="#94a3b8", linestyle="--", linewidth=.7)
            progress.text(.02, threshold, f" {name} {threshold:g}", fontsize=8,
                          transform=progress.get_yaxis_transform(), va="bottom")
    for name, aggregate in data["conditions"].items():
        for threshold, style in (("milestone", "-"), ("stretch", "--")):
            x, y = zip(*aggregate[threshold + "_curve"])
            attainment.step(x, y, where="post", color=colors[name], linestyle=style,
                            label=f"{name}: {threshold}")
    progress.set(title="Best completed validation AUC (each run)", xlabel="Elapsed seconds", ylabel="Validation ROC-AUC", xlim=(0, max(deadlines) * 1.03 if deadlines else 1))
    attainment.set(title="Threshold attainment / all runs", xlabel="Elapsed seconds", ylabel="Fraction of all runs", ylim=(-.02, 1.02))
    cost.set(title="API cost through stopping (× = incomplete lower bound)", xlabel="Known API cost, USD", ylabel="Deadline validation ROC-AUC")
    tokens.set(title="Tokens through stopping (× = incomplete subtotal)", xlabel="Input + output tokens", ylabel="Deadline validation ROC-AUC")
    for axes in (progress, attainment, cost, tokens):
        axes.grid(alpha=.15)
    if labels_seen:
        progress.legend(fontsize=7)
    if data["conditions"]:
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
        writer.writerows(runs)
    sections = ["<h1>Overnight study: validation performance at the deadline</h1>",
                "<p>Primary outcome: highest completed validation ROC-AUC within each run's scheduled allowance. "
                "Every run is listed, including failures and runs with no valid classifier. ROC-AUC measures ranking, "
                "not classification accuracy. Held-out test results are separate generalization checks.</p>"]
    sections.append(_table(["Condition", "All runs", "Valid classifiers", "Mean validation AUC (valid n)",
                            "SD (valid n)", "Milestone fraction (all runs)", "Stretch fraction (all runs)"],
                           [[name, a["run_count"], a["valid_run_count"], a["best_validation_mean"],
                             a["best_validation_sd"], a["milestone_fraction"], a["stretch_fraction"]]
                            for name, a in data["conditions"].items()]))
    sections.append("<p>Means and SD describe available classifier outcomes with valid n shown; "
                    "they do not impute a score to runs without a valid classifier. Small samples are exploratory. "
                    "Nonattainers have unknown crossing time, never the deadline as their crossing time. "
                    "Early stops carry their last completed score to the scheduled deadline; no uncompleted work is credited. "
                    "Dotted vertical lines mark allowances; dashed horizontal lines mark frozen thresholds.</p>")
    if runs:
        sections.append(_plots(data))
    else:
        sections.append("<p>No run summaries found.</p>")
    sections.append("<h2>Every run: primary outcome, thresholds, and stop reason</h2>")
    sections.append(_table(["Run", "Condition", "Repeat", "Allowance (s)", "Actual stop (s)", "Stop reason",
                            "Best validation AUC", "Milestone reached", "Milestone time (s)",
                            "Stretch reached", "Stretch time (s)", "Attempts"],
                           [[r[k] for k in ("run_id", "condition", "repeat", "allowance_seconds", "elapsed_seconds",
                                            "stop_reason", "best_validation_auc", "milestone_reached", "milestone_seconds",
                                            "stretch_reached", "stretch_seconds", "trial_attempts")] for r in runs]))
    sections.append("<h2>Held-out test confirmation (post-search)</h2>")
    sections.append(_table(["Run", "Deadline-selected test AUC", "Milestone test AUC", "Stretch test AUC", "Deadline test status"],
                           [[r[k] for k in ("run_id", "best_test_auc", "milestone_test_auc", "stretch_test_auc", "best_test_status")]
                            for r in runs]))
    sections.append("<h2>API accounting through stopping</h2><p>Dollar totals cover reported model-provider charges "
                    "for all roles, including failed calls, reviews and reflection where recorded. Unknown billing is preserved: "
                    "known cost is only a subtotal when incomplete. Training/tool compute and post-run work are recorded separately; "
                    "their monetary cost is unknown unless explicitly metered. Cached tokens are a subset of input; reasoning tokens "
                    "are a subset of output, so neither is added again. Incomplete token subtotals are not complete totals.</p>")
    sections.append(_table(["Run", "Known USD", "Complete USD total", "Input tokens", "Output tokens", "Cached tokens",
                            "Reasoning tokens", "Complete token total", "Usage complete"],
                           [[r[k] for k in ("run_id", "known_cost", "total_cost", "input_tokens", "output_tokens", "cached_tokens",
                                            "reasoning_tokens", "total_tokens", "token_usage_complete")] for r in runs]))
    sections.append("<h3>Accounting at first threshold attainment</h3>")
    sections.append(_table(["Run", "Threshold", "Reached", "Time (s)", "Known USD", "Complete USD", "Complete tokens"],
                           [[r["run_id"], name, r[name + "_reached"], r[name + "_seconds"], r[name + "_known_cost"],
                             r[name + "_total_cost"], r[name + "_total_tokens"]]
                            for r in runs for name in ("milestone", "stretch")]))
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
