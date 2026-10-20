"""Rich terminal dashboard; rendering never makes API calls or modifies agent state."""
from datetime import datetime, timezone
import os

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text


def text(value, style="", **kwargs):
    from .progress import _safe
    return Text(_safe(value), style=style, **kwargs)


def duration(seconds):
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    return f"{minutes}:{seconds:02d}"


def elapsed_now(state):
    elapsed = state.elapsed
    if state.event_at is not None and not state.stopped:
        elapsed += max(0, (datetime.now(timezone.utc) - state.event_at).total_seconds())
    return elapsed


def cost_label(state):
    account = state.accounting
    if not account:
        return "$pending"
    return f"${account.get('known_cost', 0):.4f}" + ("" if account.get("cost_complete") else " known")


def best_score(state):
    return state.best.get("score", state.best.get("validation_auc")) if state.best else None


def score_chart(state, width):
    """Two sparklines with shared explicit bounds; at most one column per trial."""
    points = list(state.history)[-max(1, width - 36):]
    values = [p[key] for p in points for key in ("score", "best") if p[key] is not None]
    if not values:
        return text("Trial scores: waiting for results\nBest so far: waiting for a selection", "dim")
    low, high = min(values), max(values)
    def line(key):
        return "".join("·" if p[key] is None else "▁▂▃▄▅▆▇█"[
            3 if high == low else min(7, max(0, round(7 * (p[key] - low) / (high - low))))] for p in points)
    result = Text()
    result.append(f"Trial scores  {line('score')} ", "cyan")
    result.append(f"range {low:.5f}–{high:.5f}\n", "dim")
    result.append(f"Best so far   {line('best')} ", "green")
    result.append(f"trials {points[0]['trial_id']}–{points[-1]['trial_id']}", "dim")
    return result


def budget(state, elapsed):
    table = Table.grid(padding=(0, 1), expand=True)
    table.add_column(style="dim", width=6)
    table.add_column(ratio=1)
    table.add_column(justify="right")
    for label, value, limit, detail, style in (
        ("Time", elapsed, state.allowance, f"{duration(elapsed)} / {duration(state.allowance)}", "cyan"),
        ("Trials", state.completed + state.unsuccessful, state.config.get("trial_cap", 0),
         f"{state.completed + state.unsuccessful} / {state.config.get('trial_cap', '?')}", "blue"),
        ("API", state.accounting.get("known_cost", 0), state.config.get("dollar_cap", 0),
         cost_label(state) + f" / ${state.config.get('dollar_cap', 0):g}",
         "cyan" if state.accounting.get("cost_complete") else "yellow"),
    ):
        bar = ProgressBar(total=limit or 1, completed=min(value, limit or 1), width=None,
                          complete_style=style, finished_style=style)
        table.add_row(label, bar, text(detail, style))
    if state.config.get("max_cores"):
        resources = state.resources
        ceiling = resources.get("max_cores", state.config["max_cores"])
        active = resources.get("active_cores", 0)
        table.add_row("CPU", ProgressBar(total=ceiling, completed=active, complete_style="cyan"),
                      text(f"{active} / {ceiling} cores", "cyan"))
    table.add_row("Tokens", Text(""), text(
        f"{state.accounting.get('input_tokens', 0):,} in / {state.accounting.get('output_tokens', 0):,} out" +
        (" ?" if state.accounting and not state.accounting.get("token_usage_complete") else ""), "dim"))
    return Panel(table, title="Budget used", border_style="blue", padding=(0, 1))


def result_panel(state):
    score = best_score(state)
    if score is None:
        return Panel(text("No selected model yet", "dim"), title="Best validation result", border_style="green")
    result = Text(f"{score:.5f}", style="bold green")
    result.append(f"  {state.objective['metric']} · trial {state.best['trial_id']}\n", "dim")
    if state.first_score is not None:
        gain = state.first_score - score if state.objective["direction"] == "minimize" else score - state.first_score
        result.append(f"Improvement {gain:+.5f}\n", "green" if gain > 0 else "dim")
    minimize = state.objective["direction"] == "minimize"
    for index, target in enumerate(state.targets[:2]):
        reached = score <= target["value"] if minimize else score >= target["value"]
        result.append(f"{'✓' if reached else '○'} {target['value']:g} {target['name']}" +
                      (" reached" if reached else " pending"), "green" if reached else "dim")
        if index == 0 and len(state.targets) > 1:
            result.append("\n")
    return Panel(result, title="Best validation result", border_style="green", padding=(0, 1))


def recent_panel(state, rows):
    table = Table(box=None, expand=True, padding=(0, 1), pad_edge=False, header_style="bold dim")
    table.add_column("Trial", width=5)
    table.add_column("Model", ratio=1, no_wrap=True, overflow="ellipsis")
    table.add_column("Score", justify="right", width=8)
    table.add_column("Outcome", width=10)
    names = {"histogram_gradient_boosting": "Gradient boosting", "random_forest": "Random forest", "logistic": "Logistic", "ridge": "Ridge"}
    for row in list(state.recent)[-rows:]:
        style = "red" if row["status"] != "completed" else "green" if row["outcome"] == "New best" else "cyan" if row["outcome"] == "Tied best" else "dim"
        model = row["config"].get("model", "—")
        table.add_row(str(row["trial_id"]), text(names.get(model, model)),
                      "—" if row["score"] is None else f"{row['score']:.5f}", text(row["outcome"], style))
    if not state.recent:
        table.add_row("—", "Waiting for first trial", "—", "")
    return Panel(table, title="Recent experiments", border_style="bright_black", padding=(0, 1))


def dashboard(state, *, width, height, spinner=None):
    """Fit the available terminal; small terminals retain activity, score and cost."""
    elapsed = elapsed_now(state)
    activity = state.activity.replace(" model call in progress", " API").replace("local ", "")
    score = best_score(state)
    if width < 50 or height < 23 or (width < 76 and height < 27):
        return Panel(Group(text(activity, "cyan", no_wrap=True),
            text(f"Best {score:.5f}" if score is not None else "No selected model yet", "bold green"),
            text(cost_label(state), "yellow" if not state.accounting.get("cost_complete") else "cyan"),
            text(f"Time {duration(elapsed)}/{duration(state.allowance)} · {state.completed} ok", "dim")),
            title="NIGHTAGENT", border_style="cyan", height=min(8, height))
    layout = Layout()
    metrics_height = (6 if width >= 76 else 12) + bool(state.config.get("max_cores"))
    recent_height = min(8, max(4, height - 3 - metrics_height - 4 - 4))
    layout.split_column(Layout(name="header", size=3), Layout(name="metrics", size=metrics_height),
        Layout(name="recent", size=recent_height), Layout(name="chart", size=4), Layout(name="findings"))
    status = Text()
    status.append(activity, "bold cyan")
    status.append(f" · {state.completed} ok / {state.unsuccessful} failed", "dim")
    if state.event_at is not None:
        age = max(0, elapsed - state.elapsed)
        status.append(f" · last event {age:.0f}s ago", "yellow" if age > 30 else "dim")
    spinner = spinner or Spinner("dots", style="cyan")
    spinner.update(text=status)
    layout["header"].update(Panel(spinner,
        title=text(f"NIGHTAGENT · {state.run_id}", "bold"),
        subtitle="LIVE FINDINGS", border_style="cyan", padding=(0, 1)))
    if width >= 76:
        layout["metrics"].split_row(Layout(budget(state, elapsed)), Layout(result_panel(state)))
    else:
        layout["metrics"].split_column(Layout(budget(state, elapsed), size=6 + bool(state.config.get("max_cores"))), Layout(result_panel(state)))
    layout["recent"].update(recent_panel(state, max(1, recent_height - 3)))
    layout["chart"].update(Panel(score_chart(state, width - 4), title="Validation trend · shared scale", border_style="bright_black", padding=(0, 1)))
    facts = Text()
    facts.append("Observed: ", "bold")
    facts.append(text(state.fact).plain)
    if state.review:
        trial, feedback = state.review
        excerpt = " ".join(text(str(feedback)).plain.split()).replace("**", "").lstrip("# ")
        facts.append(f"\nSupervisor after trial {trial} (interpretation): ", "bold magenta")
        facts.append(excerpt[:180] + ("…" if len(excerpt) > 180 else ""), "dim")
    layout["findings"].update(Panel(facts, title="Findings", border_style="magenta", padding=(0, 1)))
    return layout


class StatusLine:
    def __init__(self, stream, *, animate=True):
        self.stream = stream
        self.enabled = bool(animate and getattr(stream, "isatty", lambda: False)()
                            and os.environ.get("TERM") != "dumb")
        self.console = Console(file=stream, force_terminal=self.enabled, markup=False, highlight=False)
        self.live = None
        self.spinner = Spinner("dots", style="cyan")

    def clear(self):
        if self.live is not None:
            live, self.live = self.live, None
            live.stop()

    def write(self, value):
        self.clear()
        print(value, file=self.stream, flush=True)

    def draw(self, state, *, detailed=False):
        if not self.enabled or not state.run_id or state.stopped:
            self.clear()
            return
        size = self.console.size
        if detailed:
            content = dashboard(state, width=size.width, height=max(1, size.height - 1), spinner=self.spinner)
        else:
            self.spinner.update(text=text(f"{state.activity} | {duration(elapsed_now(state))}/{duration(state.allowance)} | {state.completed} ok | {cost_label(state)}", "cyan"))
            content = self.spinner
        if self.live is None:
            # Inline Live erases every old row before repainting, which flashes
            # in terminals that display intermediate updates (e.g. over SSH).
            # Screen mode homes the cursor and overwrites a padded frame instead.
            # Keep verbose's single status line inline with its scrolling logs.
            self.live = Live(content, console=self.console, auto_refresh=False, transient=True,
                             screen=detailed,
                             redirect_stdout=False, redirect_stderr=False, vertical_overflow="crop")
            self.live.start(refresh=True)
        else:
            self.live.update(content, refresh=True)
