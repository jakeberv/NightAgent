"""Live terminal dashboard of NightAgent runs: one row per run, plus the selected run's details.

Usage:
    python nightagent/monitor.py                          # every run under runs/
    python nightagent/monitor.py runs/fashion-mnist-pilot # one experiment folder
    python nightagent/monitor.py my-project               # a single project run with run.py

It only reads files, so it can be started, stopped and restarted at any time without affecting the
runs. A run is any folder with meetings/harness-log.jsonl. For each run it reads:
- meetings/harness-log.jsonl: the current phase, when it started, and the cost so far;
- ../logs/<run>.log (written by experiment.py): the agents' latest action, followed live;
- ../.<run>.nightagent.json: the condition (relationship), which the agents never see;
- ACTIONS.md, experiments/ and the latest meeting minutes, for the detail tabs.

Keys: up/down select a run, 1-4 switch tabs, r refreshes now, q quits.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Log, Markdown, Static, TabbedContent, TabPane

CORE = Path(__file__).resolve().parent
REFRESH_SECONDS = 2.0
QUIET_SECONDS = 15 * 60  # a running phase with no new output for this long is flagged as quiet
STATE_STYLE = {"running": "green", "quiet": "yellow", "failed": "bold red", "paused": "dim",
               "reviewing": "cyan", "done": "blue", "not started": "dim"}


# ---------------------------------------------------------------------------------------------
# Reading a run's files


@dataclass
class RunStatus:
    """What the dashboard shows for one run, read fresh from its files."""
    path: Path
    name: str
    relationship: str = "?"
    model: str = "?"
    state: str = "not started"
    phase: str = "-"
    phase_seconds: float = 0.0
    meetings: int = 0
    experiments: int = 0
    cost_usd: float = 0.0
    quiet_seconds: float = 0.0
    activity: str = ""
    error: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def console_log(self) -> Path:
        return self.path.parent / "logs" / f"{self.path.name}.log"


def find_runs(roots: list[Path]) -> list[tuple[str, Path]]:
    """Every run folder (one holding meetings/harness-log.jsonl) under the roots, with a display name."""
    found = []
    for root in roots:
        if (root / "meetings" / "harness-log.jsonl").exists():
            found.append((root.name, root))
            continue
        # Fixed depths, not "**": a run's .venv and data/ hold many thousands of files.
        for depth in ("*", "*/*", "*/*/*"):
            for log in sorted(root.glob(f"{depth}/meetings/harness-log.jsonl")):
                run = log.parent.parent
                found.append((str(run.relative_to(root)), run))
    return found


def read_events(path: Path) -> list[dict[str, Any]]:
    events = []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # a line being written right now
    return events


def tail_line(path: Path, max_bytes: int = 8192) -> str:
    """The last non-empty line of a file, read from its end."""
    with path.open("rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - max_bytes))
        lines = [l.strip() for l in f.read().decode(errors="replace").splitlines() if l.strip()]
    return lines[-1] if lines else ""


def phase_label(kind: str, number: int) -> str:
    return {"meeting": f"meeting M{number:02d}", "research": f"research wk{number}",
            "review": "review"}.get(kind, kind)


def read_status(name: str, path: Path, now: float) -> RunStatus:
    s = RunStatus(path=path, name=name)
    condition = path.parent / f".{path.name}.nightagent.json"
    if condition.exists():
        s.relationship = json.loads(condition.read_text()).get("relationship", "?")
    log = path / "meetings" / "harness-log.jsonl"
    events = read_events(log)
    s.cost_usd = sum(e.get("cost_usd", 0) or 0 for e in events if e["event"] == "turn")
    s.meetings = len(list((path / "meetings").glob("M*-minutes.md")))
    if (path / "experiments").is_dir():
        s.experiments = sum(p.is_dir() for p in (path / "experiments").iterdir())
    starts = [e for e in events if e["event"] == "run_start"]
    if starts:
        s.model = starts[-1].get("model", "?")
    phase_events = [e for e in events if e["event"] in ("phase_start", "phase_end", "phase_failed")]

    # Latest output from the agents: the console log if experiment.py wrote one, else the run log.
    sources = [p for p in (s.console_log, log) if p.exists()]
    last_write = max((p.stat().st_mtime for p in sources), default=now)
    s.quiet_seconds = now - last_write
    if s.console_log.exists():
        s.activity = tail_line(s.console_log)
    elif phase_events:
        s.activity = json.dumps(phase_events[-1])

    if not phase_events:
        return s
    last = phase_events[-1]
    s.phase = phase_label(last["phase"], last["number"])
    started = max((e for e in phase_events if e["event"] == "phase_start"), key=lambda e: e["time"], default=None)
    if started:
        s.phase_seconds = now - datetime.fromisoformat(started["time"]).timestamp()
    if (path / "review" / "scores.json").exists():
        s.state = "done"
        scores = json.loads((path / "review" / "scores.json").read_text())
        s.extra = {k: v for k, v in scores.items() if not isinstance(v, (dict, list))}
    elif last["event"] == "phase_failed":
        s.state, s.error = "failed", last.get("error", "")
    elif last["event"] == "phase_start":
        s.state = "quiet" if s.quiet_seconds > QUIET_SECONDS else ("reviewing" if last["phase"] == "review" else "running")
    else:
        s.state = "paused"  # between phases: run.py without --all, or stopped and waiting to be resumed
    return s


def fmt_age(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h{seconds % 3600 // 60:02d}m"


def experiments_summary(path: Path) -> str:
    """Markdown list of the run's experiments: name, title from its README, and whether results exist."""
    folder = path / "experiments"
    rows = []
    for exp in sorted(p for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []:
        readme = exp / "README.md"
        title = ""
        if readme.exists():
            heading = next((l for l in readme.read_text().splitlines() if l.startswith("#")), "")
            title = heading.lstrip("# ").strip()
        results = exp / "results"
        has_results = results.is_dir() and any(results.iterdir())
        mark = "results" if has_results else ("README" if readme.exists() else "in progress")
        rows.append(f"- **{exp.name}** — {title or '(no README yet)'} · _{mark}_")
    return "\n".join(rows) or "_No experiments yet._"


def latest_minutes(path: Path) -> str:
    found = []
    for p in (path / "meetings").glob("M*-minutes.md"):
        m = re.fullmatch(r"M(\d+)-minutes\.md", p.name)
        if m:
            found.append((int(m.group(1)), p))
    return max(found)[1].read_text() if found else "_No meetings yet._"


# ---------------------------------------------------------------------------------------------
# The dashboard


COLUMNS = [("run", "Run"), ("relationship", "Relationship"), ("state", "State"), ("phase", "Phase"),
           ("for", "For"), ("meetings", "Mtgs"), ("experiments", "Exps"), ("cost", "Cost"),
           ("quiet", "Quiet"), ("activity", "Latest activity")]


class Monitor(App):
    TITLE = "NightAgent monitor"
    CSS = """
    DataTable { height: auto; max-height: 50%; }
    #status { height: 1; padding: 0 1; background: $boost; }
    TabbedContent { height: 1fr; }
    Log { height: 1fr; }
    """
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_now", "Refresh"),
        Binding("1", "tab('log')", "Log"),
        Binding("2", "tab('actions')", "Actions"),
        Binding("3", "tab('experiments')", "Experiments"),
        Binding("4", "tab('minutes')", "Minutes"),
    ]

    def __init__(self, roots: list[Path]):
        super().__init__()
        self.roots = roots
        self.statuses: dict[str, RunStatus] = {}
        self.selected: str | None = None
        self.log_path: Path | None = None
        self.log_pos = 0
        self.shown: dict[str, str] = {}  # last text put in each Markdown tab, to skip needless re-renders

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield DataTable(id="runs", cursor_type="row", zebra_stripes=True)
        yield Static(id="status")
        with TabbedContent(initial="log"):
            with TabPane("Log", id="log"):
                yield Log(id="log-view", max_lines=2000)
            with TabPane("Actions", id="actions"):
                yield Markdown(id="actions-view")
            with TabPane("Experiments", id="experiments"):
                yield Markdown(id="experiments-view")
            with TabPane("Latest minutes", id="minutes"):
                yield Markdown(id="minutes-view")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one(DataTable)
        for key, label in COLUMNS:
            table.add_column(label, key=key)
        await self.refresh_all()
        self.set_interval(REFRESH_SECONDS, self.refresh_all)

    async def action_refresh_now(self) -> None:
        await self.refresh_all()

    def action_tab(self, tab: str) -> None:
        self.query_one(TabbedContent).active = tab

    async def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key.value != self.selected:
            self.selected = event.row_key.value
            self.log_path, self.log_pos = None, 0
            self.query_one("#log-view", Log).clear()
            self.shown.clear()
            await self.refresh_details()

    async def refresh_all(self) -> None:
        now = time.time()
        runs = find_runs(self.roots)
        self.statuses = {name: read_status(name, path, now) for name, path in runs}
        table = self.query_one(DataTable)
        if [str(k.value) for k in table.rows] != list(self.statuses):
            table.clear()
            for name in self.statuses:
                table.add_row(*[""] * len(COLUMNS), key=name)
        width = max(30, self.size.width - 100)
        for name, s in self.statuses.items():
            cells = {
                "run": s.name, "relationship": s.relationship,
                "state": Text(s.state, style=STATE_STYLE.get(s.state, "")),
                "phase": s.phase, "for": fmt_age(s.phase_seconds) if s.phase != "-" else "-",
                "meetings": str(s.meetings), "experiments": str(s.experiments), "cost": f"${s.cost_usd:.2f}",
                "quiet": Text(fmt_age(s.quiet_seconds), style="yellow" if s.quiet_seconds > QUIET_SECONDS else ""),
                "activity": Text((s.error or s.activity)[:width], style="red" if s.error else ""),  # not markup: logs contain [student]
            }
            for key, value in cells.items():
                table.update_cell(name, key, value)
        counts: dict[str, int] = {}
        for s in self.statuses.values():
            counts[s.state] = counts.get(s.state, 0) + 1
        self.sub_title = (f"{len(self.statuses)} runs · " + " · ".join(f"{n} {k}" for k, n in sorted(counts.items()))
                          + f" · ${sum(s.cost_usd for s in self.statuses.values()):.2f} so far")
        if not self.statuses:
            self.query_one("#status", Static).update(f"No runs found under {', '.join(map(str, self.roots))}.")
        if self.selected not in self.statuses and self.statuses:
            self.selected = next(iter(self.statuses))
        await self.refresh_details()

    async def refresh_details(self) -> None:
        s = self.statuses.get(self.selected or "")
        if s is None:
            return
        line = Text.assemble((s.name, "bold"), f" · {s.path} · model {s.model}")
        if s.extra:
            line.append(" · review: " + ", ".join(f"{k}={v}" for k, v in s.extra.items()))
        if s.error:
            line.append(f" · {s.error}", style="red")
        self.query_one("#status", Static).update(line)
        self.follow_log(s.console_log if s.console_log.exists() else s.path / "meetings" / "harness-log.jsonl")
        for view, text in (("actions", (s.path / "ACTIONS.md").read_text() if (s.path / "ACTIONS.md").exists() else ""),
                           ("experiments", experiments_summary(s.path)),
                           ("minutes", latest_minutes(s.path))):
            if self.shown.get(view) != text:
                self.shown[view] = text
                await self.query_one(f"#{view}-view", Markdown).update(text or "_Nothing yet._")

    def follow_log(self, path: Path) -> None:
        """Append the selected run's new console output to the Log tab (like tail -f)."""
        view = self.query_one("#log-view", Log)
        if path != self.log_path:
            self.log_path, self.log_pos = path, 0
            view.clear()
        if not path.exists():
            return
        size = path.stat().st_size
        if size < self.log_pos:  # the file was replaced
            self.log_pos = 0
            view.clear()
        if size > self.log_pos:
            with path.open("rb") as f:
                f.seek(self.log_pos)
                chunk = f.read()
            # Keep a partial last line for the next refresh.
            end = chunk.rfind(b"\n") + 1
            if end:
                view.write_lines(chunk[:end].decode(errors="replace").splitlines())
                self.log_pos += end


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folders", nargs="*", type=Path, default=[CORE.parent / "runs"],
                    help="experiment folders, project folders, or a folder of them (default: runs/)")
    args = ap.parse_args()
    Monitor([f.resolve() for f in args.folders]).run()


if __name__ == "__main__":
    main()
