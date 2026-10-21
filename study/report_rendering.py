"""Render report data to portable HTML, tables, and figures without reading evidence."""
from __future__ import annotations

import csv
import html
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


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


def _plots(data: dict, root: Path) -> str:
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
        name = row["analysis_group"]
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
    from .report_graphics import export_figure
    return export_figure(figure, root, "performance", "Validation progress, all-run attainment, API cost and tokens")


def _target_budget_plot(data, root):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from .report_graphics import export_figure

    figure = Figure(figsize=(12, 4.5), layout='constrained')
    FigureCanvasAgg(figure)
    for axes, field, label in zip(figure.subplots(1, 2), ('total_cost', 'total_tokens'),
                                  ('Cumulative API cost budget, USD', 'Cumulative input + output token budget')):
        for condition, aggregate in data['conditions'].items():
            for target, details in aggregate['targets'].items():
                curve = details['attainment_by_budget'][field]
                x, y = zip(*curve['curve'])
                axes.step(x, y, where='post', marker='.', label=f'{condition}: {target}')
        axes.set(xlabel=label, ylabel='Recorded attainments / all scheduled runs', ylim=(-.02, 1.02), xlim=(0, None))
        axes.grid(alpha=.15)
        axes.legend(fontsize=6)
    return export_figure(figure, root, 'target-budgets',
        'Observed budget attainment with all-run denominators. Unknown crossing accounting is excluded from the numerator; no convergence is extrapolated.')


def _efficiency_section(data, root):
    targets = [(condition, target, details) for condition, aggregate in data['conditions'].items()
               for target, details in aggregate['targets'].items()]
    sections = ['<h2>Strategy efficiency at preset targets</h2>',
        '<p>Preset targets are frozen with the problem and must be shared across strategies for comparison. '
        'Every scheduled run remains in the attainment denominator. A single repeat cannot establish a strategy ranking; '
        'repeated matched runs are needed to assess variation.</p>',
        _table(['Strategy', 'Target', 'All runs', 'Reached', 'Not observed reached', 'Fraction of all runs'],
               [[condition, target, d['n'], d['reached'], d['not_reached'], d['fraction']]
                for condition, target, d in targets]),
        '<h3>Conditional on reaching the target</h3><p>These summaries describe successful runs only, '
        'with a separate measured n for each budget; they are not an overall strategy efficiency estimate. '
        'Missing accounting is excluded, never treated as zero. Dollar budgets cover reported model API charges, '
        'not unmetered training or post-run compute.</p>',
        _table(['Strategy', 'Target', 'Budget', 'Measured successes', 'Missing successes', 'Mean', 'SD', 'Min', 'Max'],
               [[condition, target, field, *[s[key] for key in ('n', 'missing', 'mean', 'sd', 'min', 'max')]]
                for condition, target, d in targets for field, s in d['conditional_at_attainment'].items()]),
        '<p>Runs not observed to reach a target are censored at their observed end budgets; this does not '
        'estimate when or whether they would eventually succeed. Runs with no observed budget remain unknown. '
        'The budget curves count recorded attainments over all scheduled runs, not survival-adjusted probabilities; '
        'unknown crossing accounting makes them lower bounds on observed attainment by budget. '
        'There is no extrapolated convergence beyond observed budgets.</p>',
        _table(['Strategy', 'Target', 'Run not observed reached', 'Stop reason', 'Observed stop seconds',
                'Known USD subtotal', 'Complete USD', 'Complete tokens'],
               [[condition, target, *[row[key] for key in ('run_id', 'stop_reason', 'seconds', 'known_cost', 'total_cost', 'total_tokens')]]
                for condition, target, d in targets for row in d['nonattainment']['observed_end_budgets']]),
        '<h3>Budget curve accounting coverage</h3><p>Runs with unknown crossing or end budgets are excluded '
        'from those budget coordinates, while remaining in the all-run denominator.</p>',
        _table(['Strategy', 'Target', 'Budget', 'All-run denominator', 'Located attainments',
                'Attainers missing crossing budget', 'Nonattainers missing end budget'],
               [[condition, target, field, curve['denominator'], curve['known_crossings'],
                 ', '.join(curve['reached_with_unknown_budget']) or 'none',
                 ', '.join(curve['not_reached_with_unknown_end_budget']) or 'none']
                for condition, target, d in targets for field, curve in d['attainment_by_budget'].items()])]
    if targets:
        sections.append(_target_budget_plot(data, root))
    return '\n'.join(sections)


def _render_report(data: dict, root: Path) -> Path:
    """Write a portable CSV and self-contained HTML report; make no API calls."""
    started = time.perf_counter()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    runs = data["runs"]
    (root / "paired-comparisons.json").write_text(
        json.dumps(data["paired_comparisons"], indent=2, ensure_ascii=False), encoding="utf-8")
    (root / "strategy-efficiency.json").write_text(json.dumps(
        {name: aggregate['targets'] for name, aggregate in data['conditions'].items()}, indent=2), encoding='utf-8')
    fields = [key for row in runs for key in row if key not in
              ("best_curve", "postrun_accounting", "event_counts", "trace")]
    fields = list(dict.fromkeys(fields)) or ["run_id", "condition", "best_score"]
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
    from .report_graphics import overview, workflow_plot, role_plot, paired_plot
    sections.append(overview(data))
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
    sections.append(_plots(data, root) if runs else "<p>No run summaries found.</p>")
    sections.append(_efficiency_section(data, root))
    sections.append("<h2>Matched condition comparisons</h2><p>Pairs share the frozen problem, data, objective, "
                    "allowance, training seed, repeat and all settings except the declared treatment axes. "
                    "Schedule comparisons vary condition; supervisor-style comparisons also vary style. "
                    "The targeted apprentice comparison reports only its four adjacent contrasts, including "
                    "reflection without versus with lesson memory. Other protocol and configuration differences "
                    "remain separate. Duplicate units are excluded. "
                    "Differences are condition B minus condition A; a positive score difference favors B for maximization "
                    "and A for minimization. Unmatched runs and runs without valid models remain in the failure denominators.</p>")
    sections.append("<p>Exploratory 95% Student t intervals describe the mean within-pair difference, assuming independent "
                    "repeats and approximately normal differences. They are unavailable with fewer than two complete pairs "
                    "and are not adjusted for multiple comparisons. Score and cost differences use only pairs with both "
                    "measurements; cost and token differences require complete accounting. These estimates can be biased "
                    "when outcomes are missing. Target attainment includes every matched scheduled pair; crossing-time "
                    "differences use only pairs that both attained the target.</p>")
    if not data["paired_comparisons"]:
        sections.append("<p>No comparable configuration groups with two conditions are available.</p>")
    for index, comparison in enumerate(data["paired_comparisons"], 1):
        sections.append(f"<h3>Comparison {index}: {_display(comparison['condition_b'])} minus "
                        f"{_display(comparison['condition_a'])}</h3>")
        sections.append("<details><summary>Frozen configuration and matched run identifiers</summary><pre>" +
                        html.escape(json.dumps({"config": comparison["config"], "pairs": comparison["pair_ids"]},
                                              indent=2, ensure_ascii=False)) + "</pre></details>")
        sections.append(_table(["Condition", "All runs", "No valid model", "Unmatched runs", "Stop reasons"],
            [[comparison["condition_" + side], comparison["runs_" + side], comparison["no_valid_model_" + side],
              comparison["unmatched_runs_" + side], json.dumps(comparison["stop_reasons_" + side], sort_keys=True)]
             for side in ("a", "b")]))
        sections.append(f"<p>There are {comparison['matched_pairs']} matched pairs, including "
                        f"{comparison['missing_score_pairs']} pairs missing at least one valid score.</p>")
        sections.append(_table(["Measurement", "Complete pairs", "Mean B − A", "SD of differences", "95% interval"],
            [[field, value["n"], value["mean_delta"], value["sd_delta"], value["ci95"]]
             for field, value in comparison["metrics"].items()] +
            [[f"{target}: {field}", value["n"], value["mean_delta"], value["sd_delta"], value["ci95"]]
             for target, measures in comparison["targets"].items() for field, value in measures.items()]))
    if runs:
        sections.append(paired_plot(data, root))
    if runs:
        sections.append("<h2>Trial outcomes and resource use</h2><p>Completed trials have a valid score within the allowance. "
                        "Late results and missing outcomes stay separate. Resource bars sum recorded component wall time across runs; "
                        "they are not suite elapsed time or CPU-seconds. Queue waiting is excluded from local trial time. "
                        "An asterisk marks an incomplete subtotal; unknown durations are not zero.</p>")
        sections.append(workflow_plot(data, root))
    sections.append("<h2>Every run: primary outcome and stop reason</h2>")
    sections.append(_table(["Run", "Analysis group", "Protocol", "Lesson memory", "Repeat", "Allowance (s)", "Actual stop (s)", "Stop reason",
                            f"Best validation {metric}", "Attempts"],
                           [[r[k] for k in ("run_id", "analysis_group", "decision_protocol", "lesson_memory", "repeat", "allowance_seconds", "elapsed_seconds",
                                            "stop_reason", "best_score", "trial_attempts")] for r in runs]))
    sections.append("<details><summary>Frozen run configurations</summary><pre>" +
                    html.escape(json.dumps({r["run_id"]: {"analysis_group": r["analysis_group"], "config": r["config"]}
                                           for r in runs}, indent=2, ensure_ascii=False)) + "</pre></details>")
    sections.append("<h2>Literature coverage</h2><p>The literature condition makes retrieval optional. "
                    "Enabled describes the assigned condition; offered lists tools present in recorded model requests. "
                    "Attempts count recorded tool calls, including rejected requests. Successful search/fetch responses "
                    "can be empty; passages count nonempty search abstracts and fetched text. Source URLs in accepted "
                    "supervisor feedback are observable citations, not proof that evidence influenced reasoning. "
                    "Missing event logs are unknown; unexercised means no retrieval call was recorded.</p>")
    sections.append(_table(["Run", "Enabled", "Offered tools", "State", "Search attempts / successful", "Results",
                            "Fetch attempts / successful", "Passages", "Source URLs in supervisor feedback"],
        [[r["run_id"], c["enabled"], c["tools_offered"], c["state"],
          f'{c["search_attempts"]} / {c["search_successes"]}' if c["events_available"] else None,
          c["search_results"], f'{c["fetch_attempts"]} / {c["fetch_successes"]}' if c["events_available"] else None,
          c["source_passages_retrieved"], c["feedback_source_urls"]]
         for r in runs for c in [r["literature_coverage"]]]))
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
    sections.append("<h3>API usage by role</h3><p>Every recorded call attempt contributes, including retries, failures "
                    "and cancellations. Unfinished calls retain unknown usage and outcomes. Known subtotals never imply "
                    "complete accounting. The failure fraction includes failed and cancelled attempts; it is unknown "
                    "when any attempt has an unresolved outcome. Missing role records do not imply zero usage.</p>")
    sections.append(_table(["Run", "Role", "Attempts", "Completed", "Failed", "Cancelled", "Unfinished", "Unknown status",
                            "Failure fraction", "Recorded seconds", "Time complete", "Known USD", "Complete USD",
                            "Input tokens", "Output tokens", "Cached tokens", "Reasoning tokens", "Complete tokens"],
        [[r["run_id"], role] + [values[key] for key in ("attempts", "completed", "failed", "cancelled", "unfinished",
          "unknown_status", "failure_fraction", "model_seconds", "model_seconds_complete", "known_cost", "total_cost",
          "input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens", "total_tokens")]
         for r in runs for role, values in r["role_metrics"].items()]))
    if runs:
        sections.append(role_plot(data, root))
    sections.append("<h2>Recommendation uptake</h2><p>Valid decision contracts record whether the researcher followed, "
                    "modified or rejected supervisor advice. The followed fraction uses those three responses as its "
                    "denominator; not-applicable, unknown and invalid responses are separate. Without contracts, uptake is "
                    "unknown. Differences from a referenced baseline are observed validation outcomes, not evidence that "
                    "advice caused an improvement. Repeated-experiment diagnostics are observational and do not imply failure.</p>")
    sections.append(_table(["Run", "Recorded contracts", "Applicable", "Followed", "Modified", "Rejected", "Not applicable",
                            "Unknown", "Invalid", "Followed fraction"],
        [[r["run_id"]] + [r["recommendation_uptake"][key] for key in ("recorded_contracts", "applicable", "followed",
            "modified", "rejected", "not_applicable", "unknown", "invalid", "followed_fraction")] for r in runs]))
    sections.append(_table(["Run", "Trial", "Baseline", "Response", "Reason", "Trial status", "Baseline validation",
                            "Trial validation", "Observed validation difference"],
        [[r["run_id"]] + [item[key] for key in ("trial_id", "baseline_trial_id", "supervisor_response", "response_reason",
            "trial_status", "baseline_score", "trial_score", "validation_delta")]
         for r in runs for item in r["recommendation_uptake"]["outcomes"]]))
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
                    "they do not replace quantitative comparisons. In grounded_v3 runs, factual summaries and "
                    "comparison_scope come from cited records. Plans, explanations, analogies and predicted "
                    "outcomes remain unverified hypotheses, even when phrased confidently. Target status and "
                    "resource estimates are computed by the runner. Constructor effective_config describes "
                    "model settings; actual_effective_config and fit_diagnostics record actual execution.</p>")
    for row in runs:
        sections.append(f'<details><summary>{_display(row["run_id"])}</summary><pre>'
                        + html.escape(json.dumps(row["trace"], indent=2, ensure_ascii=False)) + "</pre></details>")
    if data["warnings"]:
        sections.append("<h2>Data quality notes</h2><ul>" + "".join(f"<li>{html.escape(w)}</li>" for w in data["warnings"]) + "</ul>")
    document = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
                '<title>Overnight study report</title><style>body{font:15px system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#172033}'
                'table{border-collapse:collapse;display:block;overflow-x:auto;margin:1rem 0;width:100%}th,td{padding:.55rem;border:1px solid #cbd5e1;text-align:left}'
                'th{background:#f1f5f9}img{max-width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}p{line-height:1.6}'
                '.overview{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem;margin:1.5rem 0}'
                '.card{background:#f1f5f9;border:1px solid #cbd5e1;border-top:4px solid #2563eb;border-radius:8px;padding:1rem}'
                '.card span{display:block;font-size:.85rem;color:#475569}.card strong{display:block;font-size:1.8rem;margin-top:.5rem}'
                'figure{margin:1.5rem 0}figcaption{color:#475569;font-size:.85rem}a{color:#1d4ed8}</style>'
                '<body>' + "\n".join(sections) + '</body></html>')
    output = root / "report.html"
    output.write_text(document, encoding="utf-8")
    (root / "report-accounting.json").write_text(json.dumps({
        "reporting_seconds": time.perf_counter() - started,
        "api_calls": 0, "known_api_cost": 0, "training_compute_cost": None,
        "reporting_compute_cost": None,
    }, indent=2), encoding="utf-8")
    return output


def render_report(data: dict, root: Path) -> Path:
    """Finish all rendering before atomically replacing each published artifact.

    HTML is published last and embeds its figures, so a render failure leaves the
    previous report and downloadable artifacts intact.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".report-", dir=root) as staging:
        staged = Path(staging)
        _render_report(data, staged)
        outputs = sorted((path for path in staged.rglob("*") if path.is_file()),
                         key=lambda path: (path.name == "report.html", str(path)))
        for path in outputs:
            destination = root / path.relative_to(staged)
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(path, destination)
    return root / "report.html"
