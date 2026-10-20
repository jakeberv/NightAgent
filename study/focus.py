"""A quiet, sentence-based view of the same recorded run state."""

from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from .lab import complete_sentences, sentence_summary


MODEL_NAMES = {"histogram_gradient_boosting": "gradient boosting", "random_forest": "random forest",
               "logistic": "logistic regression", "ridge": "ridge regression",
               "torch_mlp": "neural network", "torch_cnn": "convolutional network"}


def fitting_summary(value, width, lines=2, fallback="The full explanation is saved in the trace."):
    """Fit whole sentences to real terminal cells, including wide Unicode."""
    from .terminal import text
    console = Console(width=max(1, width))
    selected = ""
    for sentence in complete_sentences(sentence_summary(value, limit=2000)):
        candidate = (selected + " " + sentence.strip()).strip()
        if len(text(candidate).wrap(console, max(1, width))) <= lines:
            selected = candidate
    if selected:
        return selected
    if len(text(fallback).wrap(console, max(1, width))) <= lines:
        return fallback
    return ""  # Hide a sentence that cannot fit; never show a broken sentence.


def experiment_summary(lab):
    if lab.trial_id is None:
        return "The first experiment has not started."
    model = MODEL_NAMES.get(lab.config.get("model"), lab.config.get("model", "the selected model"))
    if lab.comparison is None:
        if isinstance(lab.intent, dict):
            return f"Trial {lab.trial_id} tests {model}; no baseline was named."
        return f"Trial {lab.trial_id} tests {model}; no completed trial is available for comparison."
    if not lab.comparison_available:
        return f"Settings for baseline trial {lab.comparison} are unavailable in this view."
    if not lab.changes:
        return f"Trial {lab.trial_id} uses the same explicit settings as completed trial {lab.comparison}."
    if len(lab.changes) == 1:
        change = lab.changes[0].replace(": ", " changes from ", 1).replace(" -> ", " to ", 1)
        return f"Compared with trial {lab.comparison}, {change}."
    return f"Trial {lab.trial_id} changes {len(lab.changes)} settings from completed trial {lab.comparison}."


def active_role(state, elapsed):
    role = state.lab.role
    names = {"researcher": "Researcher", "local": "Local experiment", "supervisor": "Supervisor", "reflection": "Reflection"}
    faces = {"researcher": ("[o_o]", "[o.o]"), "local": ("[=:=]", "[:=:]"),
             "supervisor": ("[o-O]", "[O-o]"), "reflection": ("[o~o]", "[-~-]")}
    frame = int(elapsed * 2) % 2 if state.lab.busy else 0
    return f"{faces.get(role, ('[o_o]', '[o_o]'))[frame]} {names.get(role, 'Research lab')}"


def activity_sentence(state):
    if state.activity.startswith("failure:"):
        return "The run reported a failure."
    if state.lab.busy:
        if state.lab.role == "local":
            return ("The experiment is waiting for available cores." if "Waiting" in state.lab.action else
                    f"Trial {state.lab.trial_id} is running locally.")
        return {"researcher": "The researcher is choosing the next experiment.",
                "supervisor": "The supervisor is reviewing the validation evidence.",
                "reflection": "The reflection agent is reassessing the search strategy."}.get(
                    state.lab.role, "The agent is waiting for an API response.")
    if state.lab.role in ("supervisor", "reflection") and not state.stopped:
        return state.lab.action.rstrip(".") + "."
    return state.activity[:1].upper() + state.activity[1:].rstrip(".") + "."


def narrative(state):
    """Describe recorded intent/advice, without guessing the pending response.

    Each row has a factual source label, prose, and resize priority. Advice is
    explicitly attributed and remains visible while the researcher considers it.
    """
    lab = state.lab
    guidance = lab.guidance
    if guidance and (lab.role == "researcher" or (lab.role == guidance["role"] and not lab.busy)):
        role = "Supervisor advice" if guidance["role"] == "supervisor" else "Reflection"
        after = guidance["after_trial"]
        heading = f"{role} after trial {after}" if after is not None else role
        if guidance.get('stage') == 'framing':
            heading = 'Supervisor framing'
        contract = guidance["contract"]
        fields = (("Assessment", "assessment"), ("Suggested next test", "recommendation"),
                  ("Open question", "unresolved_question")) if guidance["role"] == "supervisor" else (
                      ("Learning", "what_changed"), ("Suggested next test", "next_comparison"),
                      ("Uncertainty", "uncertainty"))
        rows = [(label, contract.get(key), 1 if index < 2 else 2)
                for index, (label, key) in enumerate(fields) if contract.get(key)]
        if guidance['role'] == 'supervisor':
            alternatives = contract.get('alternative_explanations', [])
            if alternatives:
                rows.append(('Alternatives', ' '.join(alternatives), 2))
            rows.extend((label, contract[key], 2) for label, key in (
                ('Motivation', 'motivation'), ('Cross-field connection', 'cross_field_connection'),
                ('Expected', 'expected_outcome'), ('Would weaken it', 'falsifying_outcome'),
                ('Resource limits', 'resource_check')) if contract.get(key))
        summary = contract.get("summary") or guidance["summary"]
        return heading, rows or [("Agent interpretation", summary, 1)], summary
    if lab.trial_id is None:
        return "", [], ""
    model = MODEL_NAMES.get(lab.config.get("model"), lab.config.get("model", "model"))
    heading = "Current experiment" if lab.role == "local" and lab.busy else "Last experiment"
    intent = lab.intent or {}
    rows = [("Agent hypothesis" if intent.get("hypothesis") else "Agent summary",
             intent.get("hypothesis") or lab.rationale, 1),
            ("Change", intent.get("change"), 2),
            ("Expected", intent.get("expected_outcome"), 2)]
    if not any(value for _, value, _ in rows):
        rows = [("Comparison", experiment_summary(lab), 1)]
    return f"{heading}: trial {lab.trial_id} · {model}", rows, lab.rationale or experiment_summary(lab)


def metric_value(state, value):
    return f"{value * 100:.2f}%" if state.objective["metric"] == "accuracy" else f"{value:.5f}"


def target_summary(state, score):
    if not state.targets:
        return ""
    minimize = state.objective["direction"] == "minimize"
    ordered = sorted(state.targets, key=lambda target: target["value"], reverse=minimize)
    pending = [t for t in ordered if score is None or (score > t["value"] if minimize else score < t["value"])]
    target = pending[0] if pending else ordered[-1]
    status = "reached" if not pending else "pending"
    label = f"Target {metric_value(state, target['value'])} ({target['name']})"
    if score is None or not pending:
        return f"{label}: {status}"
    gap = abs(score - target["value"])
    gap_label = f"{gap * 100:.2f} pp" if state.objective["metric"] == "accuracy" else f"{gap:.5f}"
    return f"{label} · gap {gap_label}"


def focus_dashboard(state, *, width, height, shortcut=False, chart_axis="time", ascii_only=False, run_position=""):
    from .terminal import text, elapsed_now, best_score, cost_label, duration, cpu_label, allocation_label
    from .live_chart import chart, progress_sentence
    width = min(width, 96)
    inner = max(1, width - 4)
    elapsed = elapsed_now(state)
    remaining = max(0, state.allowance - elapsed)
    score = best_score(state)
    rows = []

    def add(value, style="", priority=1):
        rows.append((text(value, style), priority))

    add(active_role(state, elapsed), "bold cyan", 3)
    add(fitting_summary(activity_sentence(state), inner, 2, "The run is active."), priority=-1)
    if state.lab.busy and state.lab.phase_started is not None:
        pending = "Local work" if state.lab.role == "local" else "API response pending"
        add(f"{pending} · {duration(max(0, elapsed - state.lab.phase_started))} elapsed", "dim", 2 if height < 23 else 0)
    add(f"{metric_value(state, score)}  best {state.objective['metric']}" if score is not None else "No selected model yet", "bold green", -1)
    if state.targets:
        add(target_summary(state, score), "cyan", 1 if height < 23 else 0)
    if width >= 60 and height >= 23:
        rows.append((chart(state, width=inner, height=10 if height >= 30 else 9,
                           axis=chart_axis, ascii_only=ascii_only), 1))
    add(fitting_summary(progress_sentence(state), inner, 2, ""), "dim", 2)
    if score is not None and state.first_score is not None and height >= 28:
        gain = state.first_score - score if state.objective["direction"] == "minimize" else score - state.first_score
        add(f"Improvement {gain:+.5f} · selected trial {state.best['trial_id']}", "dim", 2)

    heading, explanation, fallback = narrative(state)
    if heading:
        paragraphs = []
        for label, value, priority in explanation:
            prose = fitting_summary(value, max(1, inner - len(label) - 2), 2, "")
            if not prose and label == "Agent hypothesis":
                label = "Agent summary"
                prose = fitting_summary(state.lab.rationale, max(1, inner - len(label) - 2), 2, "")
            if prose:
                paragraphs.append(f"{label}: {prose}")
        if not paragraphs:
            paragraphs = [fitting_summary(fallback, inner, 2,
                           "The full explanation is available in Details.")]
        add(heading + "\n" + paragraphs[0], "magenta", 1)
        for prose in paragraphs[1:]:
            add(prose, "magenta", 3)
    from .live_lessons import visible, focus_lesson
    if visible(state):
        add(focus_lesson(state, inner, lines=3 if height >= 24 else 2), "cyan", 0 if state.lessons.latest else 2)
    # Failures remain visible even when the last valid score was excellent.
    result = state.lab.last_result
    if result and result.get("status") != "completed":
        add(fitting_summary(f"Trial {result['trial_id']} ended with status {result['status']}.", inner, 2, "The latest trial failed."), "yellow", 0)
    if state.lab.discoveries and state.lab.discoveries[-1]['style'] == 'yellow':
        add(fitting_summary(state.lab.discoveries[-1]['message'], inner, 2,
                            "An experiment warning is available in Details."), "yellow", 2)
    add(f"Time left {duration(remaining)} · API {cost_label(state)} / ${state.config.get('dollar_cap', 0):g}", "cyan", -2)
    add(f"Trials {state.completed + state.unsuccessful}/{state.config.get('trial_cap', '?')} · {state.unsuccessful} unsuccessful", "dim", -2)
    device = state.config.get('device', 'cpu')
    add(f"Host CPU {cpu_label(state)} · {allocation_label(state)} · device {device}", "dim", 3)
    if state.accounting and not state.accounting.get("cost_complete"):
        add("API total is incomplete; only known charges are shown.", "yellow", -2)

    # Remove entire blocks, preserving complete sentences and critical figures.
    console = Console(width=width)
    def lines(row):
        return max(1, len(row[0].wrap(console, inner)))
    while rows and sum(lines(row) for row in rows) > max(0, height - 2):
        remove = max(range(len(rows)), key=lambda index: (rows[index][1], index))
        rows.pop(remove)
    condition = state.config.get('condition', '').replace('_', ' ')
    title = f"FOCUS · {state.problem_id or state.run_id} · {condition}"
    if state.stopped:
        title += " · STOPPED"
    if run_position:
        # Run id is important when several strategies share a problem/dataset.
        title = f"FOCUS · {state.run_id}" + (" · STOPPED" if state.stopped else "")
    footer = "f Details · l Log · x Axis" if shortcut else "FOCUS"
    if run_position:
        footer += " · " + run_position
    return Align.center(Panel(Group(*(row[0] for row in rows)), title=text(title),
        subtitle=text(footer), border_style="cyan", padding=(0, 1), width=width))
