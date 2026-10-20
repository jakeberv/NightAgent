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


def cpu_label(state):
    value = state.cpu.get("percent")
    return f"{value:.0f}%" if value is not None else state.cpu.get("status", "sampling")


def cpu_history(state, width=30):
    return "".join("·" if value is None else "▁▂▃▄▅▆▇█"[round(value * 7 / 100)]
                   for value in state.cpu.get("history", [])[-max(1, width):]) or "—"


class CPUHistory:
    def __init__(self, state):
        self.state = state

    def __rich_console__(self, console, options):
        # Crop the oldest samples, so narrow budget cards remain current.
        yield text(cpu_history(self.state, options.max_width), "cyan", no_wrap=True)


def allocation_label(state):
    ceiling = state.resources.get("max_cores", min(state.config.get("max_cores") or 1, os.cpu_count() or 1))
    active = state.resources.get("active_cores", 0)
    return f"{active}/{ceiling} allocated"


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
    table.add_column(style="dim", width=8)
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
    value = state.cpu.get("percent")
    table.add_row("Host CPU", ProgressBar(total=100, completed=value or 0, complete_style="cyan")
                  if value is not None else Text("—"), text(cpu_label(state), "cyan"))
    table.add_row("CPU hist", CPUHistory(state),
                  text(allocation_label(state), "dim"))
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


def current_comparison(state, row):
    """Compare to the selected leader now; keep historical outcomes immutable."""
    if row['status'] != 'completed':
        return row['status'], None, 'red'
    if row['score'] is None:
        return 'Unscored', None, 'dim'
    best = best_score(state)
    if best is None or row['outcome'] == 'Unselected':
        return 'Pending', None, 'dim'
    gap = row['score'] - best if state.objective['direction'] == 'minimize' else best - row['score']
    if row['trial_id'] == state.best['trial_id']:
        return 'Best now', gap, 'bold green'
    if row['score'] == best:
        return 'Tied best', gap, 'cyan'
    return ('Prior best' if row['outcome'] == 'New best' else 'Behind'), gap, 'dim'


def recent_panel(state, rows):
    table = Table(box=None, expand=True, padding=(0, 1), pad_edge=False, header_style="bold dim")
    table.add_column("Trial", width=5)
    table.add_column("Model", ratio=1, no_wrap=True, overflow="ellipsis")
    table.add_column("Score", justify="right", width=8)
    table.add_column("Gap", justify="right", width=8)
    table.add_column("Status", width=10)
    names = {"histogram_gradient_boosting": "Gradient boosting", "random_forest": "Random forest", "logistic": "Logistic", "ridge": "Ridge"}
    for row in list(state.recent)[-rows:]:
        status, gap, style = current_comparison(state, row)
        model = row["config"].get("model", "—")
        table.add_row(str(row["trial_id"]), text(names.get(model, model)),
                      "—" if row["score"] is None else f"{row['score']:.5f}",
                      "—" if gap is None else f"{gap:.5f}", text(status, style))
    if not state.recent:
        table.add_row("—", "Waiting for first trial", "—", "—", "")
    return Panel(table, title="Recent experiments", subtitle="Gap to best · smaller is closer",
                 border_style="bright_black", padding=(0, 1))


def role_strip(state, *, expanded=False, elapsed=0):
    """Highlight actual roles; animation means activity, never percent complete."""
    lab = state.lab
    condition = state.config.get("condition")
    enabled = {"researcher", "local", "supervisor", "reflection"}
    if condition == "researcher_alone":
        enabled -= {"supervisor", "reflection"}
    elif condition in ("frequent", "periodic"):
        enabled.discard("reflection")
    stations = [("researcher", "Researcher", "[o_o]", "Choose a test"),
                ("local", "Local fit", "[=:=]", "Fit + validate"),
                ("supervisor", "Supervisor", "[o-O]", "Review evidence"),
                ("reflection", "Reflection", "[o~o]", "Reconsider")]
    if expanded:
        table = Table.grid(expand=True, padding=(0, 1))
        for _ in stations:
            table.add_column(ratio=1)
        cells = []
        for role, label, face, purpose in stations:
            active = role == lab.role
            if active and lab.busy and int(elapsed * 2) % 2:
                face = {"researcher": "[o.o]", "local": "[:=:]",
                        "supervisor": "[O-o]", "reflection": "[-~-]"}[role]
            pulse = (">" if int(elapsed * 2) % 2 else "»") if active and lab.busy else "·"
            style = "bold cyan" if active else "dim"
            cells.append(text(f"{pulse} {face} {label}\n  {purpose if role in enabled else 'Off in this condition'}", style))
        table.add_row(*cells)
        return table
    result = Text(no_wrap=True, overflow="ellipsis")
    for index, (role, label, _, _) in enumerate(stations):
        if index:
            result.append(" > ", "dim")
        result.append(("● " if role == lab.role else "") + label.replace(" experiment", "") +
                      (" (off)" if role not in enabled else ""), "bold cyan" if role == lab.role else "dim")
    return result


def experiment_panel(state, width):
    from .focus import fitting_summary, experiment_summary
    lab = state.lab
    if lab.trial_id is None:
        content = text("The first experiment has not started.", "dim")
    else:
        heading = text(f"Trial {lab.trial_id} · {lab.config.get('model', 'unspecified')} · "
                       f"preprocessing {lab.config.get('preprocessing', 'default')}", "bold cyan",
                       no_wrap=True, overflow="ellipsis")
        comparison = fitting_summary(experiment_summary(lab), width - 4, 1,
                                     f"Trial {lab.trial_id} is recorded in the trace.")
        rationale = fitting_summary(lab.rationale, width - 4 - len("Agent interpretation: "), 2, "")
        interpretation = text("Agent interpretation: " + rationale, "magenta") if rationale else text(
            "The full agent rationale is saved in the trace.", "dim")
        content = Group(heading, text(comparison, "dim"), interpretation)
    return Panel(content, title="Experiment notebook · latest trial", border_style="cyan", padding=(0, 1))


def trial_trail(state, width=116):
    rows = list(state.recent)
    # Preserve the newest outcomes when IDs or the trail outgrow the terminal.
    removed = False
    while len(rows) > 1 and 8 + sum(len(str(row["trial_id"])) + 1 for row in rows) + 3 * (len(rows) - 1) > width:
        rows.pop(0)
        removed = True
    trail = Text("Trail … " if removed else "Trail  ", style="dim", no_wrap=True, overflow="ellipsis")
    for index, row in enumerate(rows):
        if index:
            trail.append(" ─ ", "dim")
        failed = row["status"] != "completed"
        status, _, style = current_comparison(state, row)
        marker = ('×' if failed else '★' if status == 'Best now' else '↑' if status == 'Prior best'
                  else '=' if status == 'Tied best' else '·')
        trail.append(f"{marker}{row['trial_id']}", style)
    return trail


def dashboard(state, *, width, height, spinner=None, focus=False, shortcut=False, logs=False, lessons=True):
    """Fit the available terminal; small terminals retain activity, score and cost."""
    if focus:
        from .focus import focus_dashboard
        return focus_dashboard(state, width=width, height=height, shortcut=shortcut)
    from .live_lessons import visible, lesson_panel
    show_lessons = lessons and visible(state)
    if logs and width >= 40 and height >= 14:
        from .live_log import log_panel
        def log_area(area_width, area_height):
            area = Layout()
            if show_lessons and area_width >= 50 and area_height >= 11:
                lesson_height = min(14, max(6, area_height // 2))
                log_height = area_height - lesson_height
                area.split_column(Layout(log_panel(state, log_height, shortcut=shortcut), size=log_height),
                    Layout(lesson_panel(state, width=area_width, height=lesson_height), size=lesson_height))
            else:
                area.update(log_panel(state, area_height, shortcut=shortcut))
            return area
        layout = Layout()
        if width >= 132 and height >= 24:
            log_width = max(48, width * 2 // 5)
            layout.split_row(Layout(dashboard(state, width=width - log_width, height=height,
                spinner=spinner, shortcut=shortcut, lessons=False), name="overview"),
                Layout(log_area(log_width, height), size=log_width))
        else:
            log_height = max(5, min(14, height // 3))
            overview_height = height - log_height
            if overview_height < 23 or (width < 76 and overview_height < 29):
                log_height = height - 8
            layout.split_column(Layout(dashboard(state, width=width, height=height - log_height,
                spinner=spinner, shortcut=shortcut, lessons=False), name="overview"),
                Layout(log_area(width, log_height), size=log_height))
        return layout
    elapsed = elapsed_now(state)
    activity = state.activity.replace(" model call in progress", " API").replace("local ", "")
    score = best_score(state)
    if width < 50 or height < 23 or (width < 76 and height < 29):
        spinner = spinner or Spinner("dots", style="cyan")
        spinner.update(text=text(activity, "cyan", no_wrap=True))
        return Panel(Group(spinner,
            text(f"Best {score:.5f}" if score is not None else "No selected model yet", "bold green"),
            text(cost_label(state), "yellow" if not state.accounting.get("cost_complete") else "cyan"),
            text(f"Time {duration(elapsed)}/{duration(state.allowance)} · {state.completed} ok", "dim"),
            text(f"Host CPU {cpu_label(state)}", "cyan"),
            text(f"{allocation_label(state)} · {cpu_history(state, width-7-len(allocation_label(state)))}",
                 "dim", no_wrap=True, overflow="crop")),
            title="NIGHTAGENT", subtitle="f Focus · l Log" if shortcut else None, border_style="cyan", height=min(8, height))
    layout = Layout()
    metrics_height = 8 if width >= 76 else 14
    expanded = width >= 76 and height >= 32
    stations_expanded = expanded and width >= 100 and height >= 34
    header_height = 6 if stations_expanded else 4
    notebook_height = 6 if expanded else 0
    fixed_height = header_height + notebook_height + metrics_height
    chart_height = 0 if show_lessons and height - fixed_height - 4 < 11 else 4
    recent_height = min(8, max(4, height - fixed_height - chart_height - (7 if show_lessons else 6)))
    sections = [Layout(name="header", size=header_height)]
    if expanded:
        sections.append(Layout(name="experiment", size=notebook_height))
    sections.extend([Layout(name="metrics", size=metrics_height), Layout(name="recent", size=recent_height)])
    if chart_height:
        sections.append(Layout(name="chart", size=chart_height))
    sections.append(Layout(name="findings"))
    layout.split_column(*sections)
    status = Text(no_wrap=True, overflow="ellipsis")
    status.append(activity, "bold cyan")
    status.append(f" · {state.completed} ok / {state.unsuccessful} failed", "dim")
    if state.event_at is not None:
        age = max(0, elapsed - state.elapsed)
        status.append(f" · last event {age:.0f}s ago", "yellow" if age > 30 else "dim")
    spinner = spinner or Spinner("dots", style="cyan")
    spinner.update(text=status)
    header = [role_strip(state, expanded=stations_expanded, elapsed=elapsed), spinner]
    if stations_expanded:
        header.append(text(state.lab.action, "dim", no_wrap=True, overflow="ellipsis"))
    if expanded:
        layout["experiment"].update(experiment_panel(state, width))
    layout["header"].update(Panel(Group(*header),
        title=text(f"NIGHTAGENT · {state.run_id}", "bold"),
        subtitle=text(f"RESEARCH LAB · {state.problem_id or 'experiment'}" + (" · f Focus · l Log" if shortcut else "")), border_style="cyan", padding=(0, 1)))
    if width >= 76:
        layout["metrics"].split_row(Layout(budget(state, elapsed)), Layout(result_panel(state)))
    else:
        layout["metrics"].split_column(Layout(budget(state, elapsed), size=8), Layout(result_panel(state)))
    layout["recent"].update(recent_panel(state, max(1, recent_height - 3)))
    if chart_height:
        layout["chart"].update(Panel(score_chart(state, width - 4), title="Validation trend · shared scale", border_style="bright_black", padding=(0, 1)))
    if show_lessons:
        layout["findings"].update(lesson_panel(state, width=width,
            height=height - fixed_height - recent_height - chart_height))
        return layout
    from .focus import fitting_summary
    facts = Text()
    observed = fitting_summary(state.fact, width - 4 - len("Observed: "), 1,
                               f"{state.completed} experiments have completed.")
    facts.append("Observed: ", "bold")
    facts.append(text(observed))
    if state.review:
        trial, feedback = state.review
        label = "Supervisor framing: " if trial == 0 else f"Supervisor after trial {trial}: "
        summary = fitting_summary(feedback, width - 4 - len(label), 1,
                                  "Review saved.")
        facts.append("\n" + label, "bold magenta")
        facts.append(text(summary, "dim"))
    content = [facts]
    if expanded:
        content.insert(0, trial_trail(state, width - 4))
        if state.lab.discoveries:
            latest = state.lab.discoveries[-1]
            celebrating = (latest["style"] == "green" and not state.stopped and state.lab.celebration_at is not None and
                           0 <= elapsed - state.lab.celebration_at < 4)
            marker = ("✦" if int(elapsed * 2) % 2 else "✧") if celebrating else "•"
            discovery = fitting_summary(latest["message"], width - 6, 1, "A new result has been recorded.")
            content.insert(1, text(f"{marker} {discovery}", latest["style"]))
    layout["findings"].update(Panel(Group(*content), title="Findings · measured discoveries", border_style="magenta", padding=(0, 1)))
    return layout


class StatusLine:
    def __init__(self, stream, *, animate=True, input_stream=None):
        from .keyboard import ViewKeys
        self.keys = ViewKeys(input_stream)
        self.focus = False
        self.show_log = True
        self.stream = stream
        self.enabled = bool(animate and getattr(stream, "isatty", lambda: False)()
                            and os.environ.get("TERM") != "dumb")
        self.console = Console(file=stream, force_terminal=self.enabled, markup=False, highlight=False)
        self.live = None
        self.spinner = Spinner("dots", style="cyan")
        self.cpu = None

    def clear(self):
        try:
            if self.live is not None:
                live, self.live = self.live, None
                live.stop()
        finally:
            self.keys.close()

    def write(self, value):
        self.clear()
        print(value, file=self.stream, flush=True)

    def draw(self, state, *, detailed=False):
        if not self.enabled or not state.run_id or state.stopped:
            self.clear()
            return
        size = self.console.size
        if detailed:
            self.keys.start()
            if self.keys.poll() % 2:
                self.focus = not self.focus
            if self.keys.log_toggles % 2:
                if self.focus:
                    self.focus = False
                    self.show_log = True
                else:
                    self.show_log = not self.show_log
            if self.cpu is None:
                from .cpu import HostCPU
                self.cpu = HostCPU()
            state.cpu = self.cpu.sample()
            content = dashboard(state, width=size.width, height=max(1, size.height - 1), spinner=self.spinner,
                                focus=self.focus, shortcut=self.keys.active, logs=self.show_log)
        else:
            self.keys.close()
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
