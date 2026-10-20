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
        return f"The {state.lab.role} is waiting for an API response."
    return state.activity[:1].upper() + state.activity[1:].rstrip(".") + "."


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

    # Resource constraints and results outrank optional explanations on resize.
    add(active_role(state, elapsed), "bold cyan")
    add(fitting_summary(activity_sentence(state), inner, 2, "The run is active."), priority=0)
    if state.event_at is not None and elapsed - state.elapsed > 30:
        add(f"No new events for {int(elapsed - state.elapsed)} seconds.", "yellow")
    add("", priority=3)
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
    add("", priority=3)
    discovery = state.lab.discoveries[-1] if state.lab.discoveries else {"message": state.fact, "style": "dim"}
    add(fitting_summary(discovery["message"], inner, 2, "A new result has been recorded." if state.lab.discoveries else "No experiment has completed yet."), discovery["style"])
    if state.lab.trial_id is not None:
        model = MODEL_NAMES.get(state.lab.config.get("model"), state.lab.config.get("model", "model"))
        add(f"Latest experiment: trial {state.lab.trial_id} · {model}", "bold", 2)
        summary = fitting_summary(state.lab.rationale, inner - len("Agent interpretation: "), 2, "")
        if summary:
            add("Agent interpretation: " + summary, "magenta", 2)
        else:
            add(fitting_summary(experiment_summary(state.lab), inner, 2), "dim", 2)
    add("", priority=3)
    add(f"Time left {duration(remaining)} · API {cost_label(state)} / ${state.config.get('dollar_cap', 0):g}", "cyan", 0)
    add(f"Trials {state.completed + state.unsuccessful}/{state.config.get('trial_cap', '?')} · {state.unsuccessful} unsuccessful", "dim", 0)
    add(f"CPU {cpu_label(state)} · {allocation_label(state)}", "dim")
    if state.accounting and not state.accounting.get("cost_complete"):
        add("API total is incomplete; only known charges are shown.", "yellow")

    # Remove entire low-priority blocks; never crop a prose sentence at the bottom.
    console = Console(width=width)
    def lines(row):
        return max(1, len(row[0].wrap(console, inner)))
    while rows and sum(lines(row) for row in rows) > max(0, height - 2):
        remove = max(range(len(rows)), key=lambda index: (rows[index][1], index))
        rows.pop(remove)
    return Align.center(Panel(Group(*(row[0] for row in rows)), title=text(f"FOCUS · {state.run_id or state.problem_id}"),
        subtitle="f  Details" if shortcut else "FOCUS", border_style="cyan", padding=(0, 1), width=width))
