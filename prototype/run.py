"""NightAgent orchestrator: runs a student agent and a supervisor agent as separate sessions.

Usage:
    python prototype/run.py <project_dir>            # run the next phase (one meeting or one research week)
    python prototype/run.py <project_dir> --all      # run phases until the supervisor signs off
    python prototype/run.py <project_dir> --dry-run  # exercise the loop with fake agents (no API calls)

The project folder needs a QUESTION.md. On first use, the rest of nightagent/project-template/ is
copied in. Protocols (STUDENT.md, MEETING.md, SUPERVISOR.md) and the private persona are read from
nightagent/, so there is a single source of truth for agent behaviour.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "nightagent"
PERSONA = CORE / "supervisor-persona.md"
TEMPLATE_SKIP = {"CLAUDE.md", ".claude", ".gitkeep", ".DS_Store"}
END_MARKER = "END MEETING"

STUDENT_HARNESS_NOTE = f"""
# How this harness runs (overrides the mechanics described above)

- An orchestrator program runs the project one phase at a time, each in a fresh session. It tells you the
  current phase in its first message. Ignore STUDENT.md's "Running the project" table and the operator
  commands ("run the project", "next step"): the orchestrator decides the phase.
- Your supervisor is a separate agent run by the orchestrator, not a subagent. Do not use the Agent tool.
  In a meeting, the text of each of your replies is relayed verbatim to the supervisor, and its reply comes
  back to you as the next message. Write each reply as a message to your supervisor.
- When everything in the meeting is agreed, end your message with a line containing only: {END_MARKER}
- The orchestrator writes `meetings/MNN-transcript.md` itself. Do not write or edit transcripts. You still
  write the minutes, `ACTIONS.md` and `memory/` after each meeting.
- Your session ends after each phase, so anything you need later must be written to files.
- The supervisor's persona file is blocked for you, and you can only write inside this project folder.
"""

SUPERVISOR_HARNESS_NOTE = """
# How this harness runs

- The orchestrator relays the student's messages to you, and your replies (verbatim) to the student.
- You are a fresh agent for every meeting, with no memory of earlier meetings except the project files:
  read them as described under "Before every reply".
- Your working directory is the project folder. You can read files (including figures), not write them.
"""


# ---------------------------------------------------------------------------------------------
# Project state


@dataclass
class Phase:
    kind: str  # "meeting", "research" or "done"
    number: int  # meeting number, or the number of the brief the research week will end with


def init_project(project: Path) -> None:
    """Copy missing template files into the project (never overwrites)."""
    if not (project / "QUESTION.md").is_file():
        sys.exit(f"Error: {project}/QUESTION.md not found: write the question first.")
    for src in (CORE / "project-template").rglob("*"):
        rel = src.relative_to(CORE / "project-template")
        if any(part in TEMPLATE_SKIP for part in rel.parts):
            continue
        dst = project / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        elif not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    (project / "meetings").mkdir(exist_ok=True)


def meeting_files(project: Path, kind: str) -> dict[int, Path]:
    found = {}
    for p in (project / "meetings").glob(f"M*-{kind}.md"):
        m = re.fullmatch(rf"M(\d+)-{kind}\.md", p.name)
        if m:
            found[int(m.group(1))] = p
    return found


def next_phase(project: Path) -> Phase:
    minutes = meeting_files(project, "minutes")
    briefs = meeting_files(project, "brief")
    if any("Signed off" in p.read_text() for p in minutes.values()):
        return Phase("done", max(minutes))
    if 0 not in minutes:
        return Phase("meeting", 0)
    latest_minutes = max(minutes)
    pending = [n for n in briefs if n > latest_minutes]
    if pending:
        return Phase("meeting", min(pending))
    return Phase("research", latest_minutes + 1)


# ---------------------------------------------------------------------------------------------
# Agents


def read(name: str) -> str:
    return (CORE / name).read_text()


class Agent:
    """One Claude Code session (via the Agent SDK). `send` returns the final text of the turn."""

    def __init__(self, role: str, project: Path, log: "RunLog", model: str | None, effort: str | None):
        self.role, self.project, self.log = role, project, log
        self.model, self.effort = model, effort
        self.client = None

    def options(self):
        from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

        common = dict(cwd=str(self.project), setting_sources=[], model=self.model, effort=self.effort)
        if self.role == "student":
            prompt = "\n\n".join([read("STUDENT.md"), read("MEETING.md"), read("SUPERVISOR.md"), STUDENT_HARNESS_NOTE])
            return ClaudeAgentOptions(
                system_prompt={"type": "preset", "preset": "claude_code", "append": prompt},
                permission_mode="bypassPermissions",
                disallowed_tools=["Agent", "Task"],
                hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[self.guard_student])]},
                **common,
            )
        prompt = "\n\n".join([read("SUPERVISOR.md"), read("MEETING.md"), PERSONA.read_text(), SUPERVISOR_HARNESS_NOTE])
        return ClaudeAgentOptions(
            system_prompt=prompt,
            tools=["Read", "Glob", "Grep"],
            allowed_tools=["Read", "Glob", "Grep"],
            permission_mode="dontAsk",
            **common,
        )

    async def guard_student(self, hook_input: dict[str, Any], tool_use_id: str | None, context: Any) -> dict[str, Any]:
        """Block the persona file and any write outside the project folder."""
        tool, args = hook_input["tool_name"], hook_input["tool_input"]
        reason = None
        if "supervisor-persona" in json.dumps(args):
            reason = "The supervisor's persona is private."
        elif tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            target = Path(args.get("file_path") or args.get("notebook_path") or "")
            target = target if target.is_absolute() else self.project / target
            if not target.resolve().is_relative_to(self.project):
                reason = "You can only write inside your project folder."
        if reason:
            self.log.event("blocked", role=self.role, tool=tool, reason=reason)
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                           "permissionDecisionReason": reason}}
        return {}

    async def start(self) -> None:
        from claude_agent_sdk import ClaudeSDKClient

        self.client = ClaudeSDKClient(self.options())
        await self.client.connect()

    async def send(self, text: str) -> str:
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

        await self.client.query(text)
        result = ""
        async for msg in self.client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, ToolUseBlock):
                        print(f"    [{self.role}] {block.name} {short(block.input)}")
                    elif isinstance(block, TextBlock) and block.text.strip():
                        print(f"    [{self.role}] {short(block.text)}")
            elif isinstance(msg, ResultMessage):
                result = msg.result or ""
                self.log.event("turn", role=self.role, session=msg.session_id, cost_usd=msg.total_cost_usd,
                               turns=msg.num_turns, error=msg.is_error)
        return result.strip()

    async def close(self) -> None:
        if self.client:
            await self.client.disconnect()


class FakeAgent:
    """Stand-in for Agent in --dry-run: writes the files a real agent would, without API calls."""

    def __init__(self, role: str, project: Path, log: "RunLog", *_: Any):
        self.role, self.project, self.log, self.turns = role, project, log, 0

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def send(self, text: str) -> str:
        self.turns += 1
        self.log.event("turn", role=self.role, session="dry-run", cost_usd=0.0, turns=1, error=False)
        m = re.search(r"Phase: (meeting|research|minutes) M(\d+)", text)
        if self.role == "supervisor":
            if self.turns == 1:
                self.meeting = int(re.search(r"Meeting M(\d+)", text).group(1))
                return "Feedback: show me the figures."
            return "Agreed. Signed off." if self.meeting >= 2 else "Agreed."
        if m and m.group(1) == "research":
            (self.project / "meetings" / f"M{int(m.group(2)):02d}-brief.md").write_text("# Brief (dry run)\n")
            return "Research done; brief written."
        if m and m.group(1) == "minutes":
            n = int(m.group(2))
            signed = "Signed off" in (self.project / "meetings" / f"M{n:02d}-transcript.md").read_text()
            (self.project / "meetings" / f"M{n:02d}-minutes.md").write_text(
                f"# M{n:02d} (dry run)\n" + ("Supervisor: Signed off\n" if signed else ""))
            return "Minutes written."
        if "Agreed" in text:
            return f"Thanks.\n{END_MARKER}"
        return "Here is my update." if self.turns == 1 else "Proposed actions: make the figures. Agreed?"


# ---------------------------------------------------------------------------------------------
# Phases


class RunLog:
    """Append-only JSONL log of the run, written into the project (meetings/harness-log.jsonl)."""

    def __init__(self, project: Path):
        self.path = project / "meetings" / "harness-log.jsonl"

    def event(self, kind: str, **data: Any) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"), "event": kind, **data}) + "\n")


def short(x: Any, n: int = 100) -> str:
    s = x if isinstance(x, str) else json.dumps(x)
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


async def run_meeting(project: Path, n: int, make_agent, log: RunLog, max_messages: int) -> None:
    mid = f"M{n:02d}"
    transcript = project / "meetings" / f"{mid}-transcript.md"
    transcript.write_text(f"# {mid} transcript\n\n_Written by the NightAgent orchestrator: every message, verbatim._\n")

    def record(speaker: str, text: str) -> None:
        with transcript.open("a") as f:
            f.write(f"\n## {speaker}\n\n{text}\n")
        print(f"  {speaker}: {short(text, 300)}")

    kind = "kickoff meeting" if n == 0 else "supervision meeting"
    student, supervisor = make_agent("student"), make_agent("supervisor")
    await student.start()
    await supervisor.start()
    try:
        message = await student.send(
            f"Phase: meeting {mid} ({kind}). Prepare as MEETING.md describes (read the project files first), "
            f"then write your opening message to your supervisor.")
        record("Student", message)
        reply = await supervisor.send(f"Meeting {mid} ({kind}). Your student says:\n\n{message}")
        record("Supervisor", reply)
        for _ in range(max_messages):
            message = await student.send(f"Your supervisor says:\n\n{reply}")
            done = END_MARKER in message
            record("Student", message.replace(END_MARKER, "").strip())
            if done:
                break
            reply = await supervisor.send(f"Your student says:\n\n{message}")
            record("Supervisor", reply)
        else:
            log.event("meeting_cut_off", meeting=mid, max_messages=max_messages)
            print(f"  Meeting {mid} hit the {max_messages}-message safety limit.")
        await student.send(
            f"Phase: minutes {mid}. The meeting is over; the orchestrator saved the verbatim transcript at "
            f"{transcript.relative_to(project)}. Now write meetings/{mid}-minutes.md, update ACTIONS.md and memory/ "
            f"(and QUESTION.md clarifications after the kickoff), as MEETING.md describes. If the supervisor said "
            f"\"Signed off\", say so in the minutes.")
    finally:
        await student.close()
        await supervisor.close()


async def run_research(project: Path, n: int, make_agent) -> None:
    student = make_agent("student")
    await student.start()
    try:
        await student.send(
            f"Phase: research M{n:02d}. Carry out the actions agreed at the last meeting, following STUDENT.md "
            f"(if the supervisor asked you to write up, finish REPORT.md as a complete paper instead). "
            f"Finish by writing meetings/M{n:02d}-brief.md for the next meeting.")
    finally:
        await student.close()


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path, help="project folder containing QUESTION.md")
    ap.add_argument("--all", action="store_true", help="run phases until the supervisor signs off")
    ap.add_argument("--dry-run", action="store_true", help="use fake agents (no API calls)")
    ap.add_argument("--model", default="claude-opus-5-5", help="model for both agents")
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--max-meeting-messages", type=int, default=20,
                    help="safety limit on student replies per meeting (guards against a runaway loop)")
    args = ap.parse_args()

    project = args.project.resolve()
    init_project(project)
    log = RunLog(project)
    agent_cls = FakeAgent if args.dry_run else Agent

    def make_agent(role: str):
        return agent_cls(role, project, log, args.model, args.effort)

    while True:
        phase = next_phase(project)
        if phase.kind == "done":
            print("Project signed off.")
            return
        label = f"meeting M{phase.number:02d}" if phase.kind == "meeting" else f"research week → M{phase.number:02d} brief"
        print(f"== {label}")
        log.event("phase_start", phase=phase.kind, number=phase.number)
        if phase.kind == "meeting":
            await run_meeting(project, phase.number, make_agent, log, args.max_meeting_messages)
            if not (project / "meetings" / f"M{phase.number:02d}-minutes.md").exists():
                sys.exit(f"Student did not write M{phase.number:02d}-minutes.md; stopping.")
        else:
            await run_research(project, phase.number, make_agent)
            if not (project / "meetings" / f"M{phase.number:02d}-brief.md").exists():
                sys.exit(f"Student did not write M{phase.number:02d}-brief.md; stopping.")
        log.event("phase_end", phase=phase.kind, number=phase.number)
        if not args.all:
            return


if __name__ == "__main__":
    asyncio.run(main())
