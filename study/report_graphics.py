"""Portable figures and overview cards built only from frozen report records."""
import base64
import html
import io
from pathlib import Path
import textwrap


def export_figure(figure, root, name, description):
    directory = Path(root) / "figures"
    directory.mkdir(exist_ok=True)
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=150, facecolor="white")
    pixels = buffer.getvalue()
    (directory / f"{name}.png").write_bytes(pixels)
    figure.savefig(directory / f"{name}.svg", format="svg", facecolor="white")
    encoded = base64.b64encode(pixels).decode("ascii")
    return (f'<figure><img alt="{html.escape(description, quote=True)}" '
            f'src="data:image/png;base64,{encoded}"><figcaption>{html.escape(description)} · '
            f'<a download href="figures/{name}.png">PNG</a> · '
            f'<a download href="figures/{name}.svg">SVG</a></figcaption></figure>')


def overview(data):
    rows = data["runs"]
    scores = [r["best_score"] for r in rows if r["best_score"] is not None]
    costs = [r["known_cost"] for r in rows if r["known_cost"] is not None]
    best = (max if data["objective"]["direction"] == "maximize" else min)(scores) if scores else None
    complete = bool(rows) and all(r["cost_complete"] and r["known_cost"] is not None for r in rows)
    cards = [("Runs with a valid model", f"{len(scores)} / {len(rows)}"),
             ("Completed trials within allowance", str(sum(r["valid_completed_trials"] for r in rows))),
             (f"Best validation {data['objective']['metric']} ({data['objective']['direction']})",
              f"{best:.6g}" if best is not None else "unknown"),
             ("API cost" if complete else "Known API cost · incomplete subtotal",
              f"${sum(costs):.4f}" if costs else "unknown")]
    return '<div class="overview">' + ''.join(
        f'<div class="card"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>'
        for label, value in cards) + '</div>'


def workflow_plot(data, root):
    # report._plots configures the headless matplotlib directory before this call.
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.ticker import MaxNLocator
    from matplotlib.patches import Patch

    groups = [(name, [r for r in data["runs"] if r["analysis_group"] == name]) for name in data["conditions"]]
    figure = Figure(figsize=(13, max(4.5, 1.15 * len(groups) + 1.8)), layout="constrained")
    FigureCanvasAgg(figure)
    outcomes, resources = figure.subplots(1, 2)
    labels = [textwrap.fill(name.replace('_', ' '), 24) for name, _ in groups]
    colors = {"Completed": "#059669", "Failed": "#dc2626", "Timed out": "#d97706",
              "Late": "#9333ea", "Other / unknown": "#64748b"}
    left = [0] * len(groups)
    for label, color in colors.items():
        counts = [sum(row["trial_outcomes"][label] for row in rows) for _, rows in groups]
        bars = outcomes.barh(range(len(groups)), counts, left=left, label=label, color=color, height=.58)
        for bar, count in zip(bars, counts):
            if count:
                outcomes.text(bar.get_x() + bar.get_width()/2, bar.get_y() + bar.get_height()/2,
                              str(count), ha="center", va="center", color="white", fontsize=9)
        left = [start + count for start, count in zip(left, counts)]
    outcomes.set(title="What happened to the trials?", xlabel="Recorded attempts", yticks=range(len(groups)), yticklabels=labels)
    outcomes.set_xlim(0, max(1, max(left, default=0) * 1.05))
    outcomes.xaxis.set_major_locator(MaxNLocator(integer=True))
    outcomes.legend(loc="upper left", bbox_to_anchor=(0, -.14), ncols=2, fontsize=8, frameon=False)
    components = [("model_seconds", "Model calls", "#2563eb"),
                  ("training_seconds", "Local trials", "#059669"),
                  ("queue_seconds", "CPU queue", "#d97706")]
    for index, (field, label, color) in enumerate(components):
        for group, (_, rows) in enumerate(groups):
            values = [r[field] for r in rows if r[field] is not None]
            y = group + (index - 1) * .23
            complete = len(values) == len(rows) and all(r.get(field + "_complete", True) for r in rows)
            if values:
                total = sum(values)
                resources.barh(y, total, height=.2, color=color, label=label if group == 0 else None)
                resources.annotate(f"{total:.1f}" + ("*" if not complete else ""), (total, y),
                                   xytext=(4, 0), textcoords="offset points", va="center", fontsize=8)
            else:
                resources.plot([], [], color=color, linewidth=6, label=label if group == 0 else None)
                resources.annotate("unknown", (0, y), xytext=(4, 0), textcoords="offset points",
                                   va="center", fontsize=8, color=color)
    resources.set(title="Where did recorded time go?", xlabel="Component wall seconds (sum across runs)",
                  yticks=range(len(groups)), yticklabels=labels)
    resources.set_xlim(0, max(1, resources.get_xlim()[1]) * 1.25)
    resources.legend(handles=[Patch(color=color, label=label) for _, label, color in components],
                     loc="upper left", bbox_to_anchor=(0, -.14), ncols=3, fontsize=8, frameon=False)
    for axes in (outcomes, resources):
        # Annotations alone do not expand limits: keep unknown/zero components
        # visible even when no bar exists for the first or final component.
        axes.set_ylim(-.5, len(groups)-.5)
        axes.invert_yaxis()
        axes.grid(axis="x", alpha=.15)
        axes.set_axisbelow(True)
        axes.spines[["top", "right"]].set_visible(False)
    return export_figure(figure, root, "workflow", "Trial outcomes and recorded resource time; * means incomplete subtotal")


def role_plot(data, root):
    """Show observed role costs without replacing unknown measurements with zero."""
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    rows = [(row["run_id"], role, values) for row in data["runs"]
            for role, values in row["role_metrics"].items()]
    if not rows:
        return "<p>No role-level call records are available.</p>"
    figure = Figure(figsize=(15, max(4, .48 * len(rows) + 1.7)), layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots(1, 4)
    labels = [textwrap.fill(f"{run} / {role}", 30) for run, role, _ in rows]
    specs = [("model_seconds", "model_seconds_complete", "Recorded model seconds", "#2563eb"),
             ("input_tokens", "token_usage_complete", "Input + output tokens", "#059669"),
             ("known_cost", "cost_complete", "Known API cost (USD)", "#9333ea"),
             ("failure_fraction", "status_complete", "Failed or cancelled / attempts", "#dc2626")]
    for axis, (field, complete_field, title, color) in zip(axes, specs):
        for y, (_, _, values) in enumerate(rows):
            value = values[field]
            if field == "input_tokens":
                value = (values["input_tokens"] + values["output_tokens"]
                         if values["input_tokens"] is not None and values["output_tokens"] is not None else None)
            if value is None:
                axis.annotate("unknown", (0, y), xytext=(4, 0), textcoords="offset points", va="center", fontsize=8)
                continue
            axis.barh(y, value, color=color, height=.6)
            label = (f"{values['failed'] + values['cancelled']} / {values['attempts']}"
                     if field == "failure_fraction" else f"{value:.4g}")
            axis.annotate(label + ("*" if not values[complete_field] else ""), (value, y),
                          xytext=(4, 0), textcoords="offset points", va="center", fontsize=8)
        axis.set(title=title, yticks=range(len(rows)), yticklabels=labels if axis is axes[0] else [])
        axis.set_ylim(len(rows) - .5, -.5)
        axis.set_xlim(0, 1.3 if field == "failure_fraction" else max(axis.get_xlim()[1], .01) * 1.4)
        axis.grid(axis="x", alpha=.15)
        axis.set_axisbelow(True)
        axis.spines[["top", "right"]].set_visible(False)
    return export_figure(figure, root, "roles",
        "Recorded API time, tokens, cost and failure fraction by run and role; * marks incomplete subtotals.")


def paired_plot(data, root):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    comparisons = data["paired_comparisons"]
    if not comparisons:
        return ""
    figure = Figure(figsize=(12, max(3.8, .65 * len(comparisons) + 1.7)), layout="constrained")
    FigureCanvasAgg(figure)
    axis = figure.subplots()
    labels = []
    for y, comparison in enumerate(comparisons):
        summary = comparison["metrics"]["best_score"]
        labels.append(textwrap.fill(f"{y + 1}. {comparison['condition_b']} − {comparison['condition_a']} "
                                   f"(n={summary['n']}/{comparison['matched_pairs']})", 48))
        average, interval = summary["mean_delta"], summary["ci95"]
        if average is None:
            axis.annotate("No paired scores", (0, y), xytext=(6, 0), textcoords="offset points", va="center")
        elif interval is None:
            axis.plot(average, y, "o", color="#2563eb")
        else:
            axis.errorbar(average, y, xerr=[[average - interval[0]], [interval[1] - average]],
                          fmt="o", color="#2563eb", capsize=4)
    axis.axvline(0, color="#64748b", linestyle=":")
    axis.set(yticks=range(len(comparisons)), yticklabels=labels,
             title="Matched validation differences and exploratory 95% intervals",
             xlabel=f"Condition B − condition A in {data['objective']['metric']} ({data['objective']['direction']})")
    axis.set_ylim(len(comparisons) - .5, -.5)
    axis.grid(axis="x", alpha=.15)
    axis.spines[["top", "right"]].set_visible(False)
    return export_figure(figure, root, "paired",
        "Paired validation differences use complete score pairs; n shows scored pairs over all matched pairs. "
        "Intervals require at least two pairs; configuration numbers refer to the comparison tables.")
