"""A quiet, sentence-based view of the same recorded run state."""

from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from .lab import complete_sentences, sentence_summary


MODEL_NAMES = {"histogram_gradient_boosting": "gradient boosting", "random_forest": "random forest",
               "logistic": "logistic regression", "ridge": "ridge regression"}


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
        contract = guidance["contract"]
        fields = (("Assessment", "assessment"), ("Suggested next test", "recommendation"),
                  ("Open question", "unresolved_question")) if guidance["role"] == "supervisor" else (
                      ("Learning", "what_changed"), ("Suggested next test", "next_comparison"),
                      ("Uncertainty", "uncertainty"))
        rows = [(label, contract.get(key), 1 if index < 2 else 2)
                for index, (label, key) in enumerate(fields) if contract.get(key)]
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


def focus_dashboard(state, *, width, height, shortcut=False):
    from .terminal import text, elapsed_now, best_score, cost_label, duration, cpu_label, allocation_label
    width = min(width, 96)
    inner = max(1, width - 4)
    elapsed = elapsed_now(state)
    remaining = max(0, state.allowance - elapsed)
    score = best_score(state)
    rows = []

    def add(value, style="", priority=1):
        rows.append((text(value, style), priority))

    # Keep the explanation ahead of decoration and resource detail on resize.
    add(active_role(state, elapsed), "bold cyan", 3)
    add(fitting_summary(activity_sentence(state), inner, 2, "The run is active."), priority=0)
    if state.lab.busy and state.lab.phase_started is not None:
        pending = "Local work" if state.lab.role == "local" else "API response pending"
        add(f"{pending} · {duration(max(0, elapsed - state.lab.phase_started))} elapsed", "dim", 2)
    add("", priority=4)
    heading, explanation, fallback = narrative(state)
    if heading:
        # Group the source label with its prose so resizing never orphans it.
        paragraphs = []
        for label, value, priority in explanation:
            prose = fitting_summary(value, max(1, inner - len(label) - 2),
                                    3 if height >= 28 else 2, "")
            if not prose and label == "Agent hypothesis":
                label = "Agent summary"
                prose = fitting_summary(state.lab.rationale, max(1, inner - len(label) - 2), 2, "")
            if prose:
                paragraphs.append((f"{label}: {prose}", priority))
        if not paragraphs:
            paragraphs = [(fitting_summary(fallback, inner, 2,
                           "The full explanation is available in Details."), 1)]
        first, priority = paragraphs[0]
        add(heading + "\n" + first, "magenta", priority)
        for prose, priority in paragraphs[1:]:
            add(prose, "magenta", priority)
    add("", priority=4)
    add(f"{score:.5f}  best {state.objective['metric']}" if score is not None else "No selected model yet", "bold green", 0)
    if score is not None and state.first_score is not None:
        gain = state.first_score - score if state.objective["direction"] == "minimize" else score - state.first_score
        add(f"Improvement {gain:+.5f} · selected trial {state.best['trial_id']}", "dim", 2)
    if state.targets:
        minimize = state.objective["direction"] == "minimize"
        targets = []
        for target in state.targets[:2]:
            reached = score is not None and (score <= target["value"] if minimize else score >= target["value"])
            targets.append(f"{target['name']} {target['value']:g}: {'reached' if reached else 'pending'}")
        add(" · ".join(targets), "dim", 2)
    # Measurements stay distinct from agent expectations and incidental warnings.
    from .lab import score_of
    result = state.lab.last_result
    if result and result.get("status") != "completed":
        evidence = f"Trial {result['trial_id']} ended with status {result['status']}."
    elif result and score_of(result) is not None:
        evidence = f"Trial {result['trial_id']} measured {score_of(result):.5f} validation {state.objective['metric']}."
    else:
        evidence = state.fact
    add(fitting_summary(evidence, inner, 2, "A result has been recorded." if result else
                        "No experiment has completed yet."), "dim", 1)
    if state.lab.discoveries:
        discovery = state.lab.discoveries[-1]
        add(fitting_summary(discovery["message"], inner, 2, "A new result has been recorded."),
            discovery["style"], 2)
    add("", priority=4)
    add(f"Time left {duration(remaining)} · API {cost_label(state)} / ${state.config.get('dollar_cap', 0):g}", "cyan", 0)
    add(f"Trials {state.completed + state.unsuccessful}/{state.config.get('trial_cap', '?')} · {state.unsuccessful} unsuccessful", "dim", 0)
    add(f"CPU {cpu_label(state)} · {allocation_label(state)}", "dim", 3)
    if state.accounting and not state.accounting.get("cost_complete"):
        add("API total is incomplete; only known charges are shown.", "yellow", 0)

    # Remove entire low-priority blocks; never crop a prose sentence at the bottom.
    console = Console(width=width)
    def lines(row):
        return max(1, len(row[0].wrap(console, inner)))
    while rows and sum(lines(row) for row in rows) > max(0, height - 2):
        remove = max(range(len(rows)), key=lambda index: (rows[index][1], index))
        rows.pop(remove)
    return Align.center(Panel(Group(*(row[0] for row in rows)), title=text(f"FOCUS · {state.run_id or state.problem_id}"),
        subtitle="f  Details · l  Log" if shortcut else "FOCUS", border_style="cyan", padding=(0, 1), width=width))
