"""NightAgent orchestrator: runs a student agent and a supervisor agent as separate Claude Code sessions.

Usage:
    python nightagent/run.py <project_dir>            # run the next phase (one meeting or one research week)
    python nightagent/run.py <project_dir> --all      # run phases until the supervisor signs off
    python nightagent/run.py <project_dir> --dry-run  # exercise the loop with fake agents (no API calls)
    python nightagent/run.py <project_dir> --provider openrouter   # bill OpenRouter (key in .env or env)

The project folder needs a QUESTION.md. On first use, the rest of nightagent/project-template/ is
copied in. Protocols (STUDENT.md, MEETING.md, SUPERVISOR.md) and the private persona are read from
this folder; they describe how the orchestrator runs meetings and phases.

Design decisions:
- Two separate agents. The student and supervisor are independent Claude Code sessions (via the
  Claude Agent SDK). In a meeting this program relays each message verbatim between them and writes
  the transcript itself, so the record of what the supervisor said is not written by the student.
- A fresh session for every phase. No conversation context survives from one phase to the next, so
  the project files (memory/, minutes, ACTIONS.md, experiments/) are the agents' only memory. This
  makes the effect of the memory files testable.
- All state lives in the project folder. The next phase is derived from the files in meetings/, so a
  run can be stopped at any time and resumed by running the same command again.
- Only the supervisor sees the persona. It is part of the supervisor's system prompt; the student is
  never given it, and a hook blocks the student's tool calls that name the persona file.
- Isolation from the machine's own Claude Code configuration: setting_sources=[] means neither agent
  loads CLAUDE.md files or settings.json, so behaviour depends only on the files in nightagent/.
- Containment: the owner's own Claude Code policy is applied explicitly (SANDBOX, PERMISSIONS): Bash
  runs in the OS sandbox (writes only inside the project) with no way to opt out, bypass-permissions
  mode is off, and reads outside the project folder are blocked. The student runs in "dontAsk" mode,
  so anything that would need a human's approval is denied rather than waiting.
- Billing: by default the agents use whatever Claude Code is logged in with (a Claude subscription) or
  ANTHROPIC_API_KEY. With --provider openrouter they are pointed at OpenRouter's Anthropic-compatible
  endpoint instead, using OPENROUTER_API_KEY from the environment or the repository's .env file
  (never a command-line argument, so the key stays out of shell history and process listings).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

CORE = Path(__file__).resolve().parent  # nightagent/: protocols, persona, template
PERSONA = CORE / "supervisor-persona.md"
TEMPLATE_SKIP = {".gitkeep", ".DS_Store"}  # placeholder/OS files not copied into projects
END_MARKER = "END MEETING"  # the student ends a meeting with this line (see MEETING.md)
SIGN_OFF = "Signed off"  # the supervisor ends the project with this phrase (see SUPERVISOR.md)
DEFAULT_MODELS = {  # per provider; override with --model (OpenRouter uses its own model names)
    "claude": "claude-opus-5-5",
    "openrouter": "~anthropic/claude-opus-latest[1m]",  # OpenRouter's alias; [1m] = 1M-token context
}
# The repository owner's Claude Code policy (~/.claude/settings.json), applied explicitly to both agents
# because setting_sources=[] skips that file: Bash always runs in the OS sandbox with no escape hatch,
# bypass-permissions mode is off, and tools can't read outside the project folder.
SANDBOX = {
    "enabled": True,
    "failIfUnavailable": True,  # refuse to start rather than run unsandboxed
    "allowUnsandboxedCommands": False,  # no dangerouslyDisableSandbox
}
# One message from Claude Code can carry a whole tool result (e.g. a figure the agent reads); the SDK's
# 1 MB default would end the phase with an error.
MAX_MESSAGE_BYTES = 64 * 1024 * 1024
PERMISSIONS = {"blockReadsOutsideWorkingDirectories": True, "disableBypassPermissionsMode": "disable"}
# With bypass mode off, the student runs in "dontAsk": these tools are allowed, anything else is denied.
STUDENT_TOOLS = ["Bash", "Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep",
                 "WebSearch", "WebFetch", "TodoWrite"]


def load_dotenv(path: Path = CORE.parent / ".env") -> None:
    """Load KEY=VALUE lines from the repository's .env (gitignored) without overriding the environment."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key.removeprefix("export ").strip(), value.strip().strip("'\""))


def provider_env(provider: str) -> dict[str, str]:
    """Environment for the agents' Claude Code processes (merged over this process's environment).

    "claude": nothing extra; Claude Code uses its login or ANTHROPIC_API_KEY.
    "openrouter": the settings from OpenRouter's Claude Code guide. ANTHROPIC_API_KEY must be set to
    an empty string, or Claude Code may fall back to authenticating with Anthropic directly.
    """
    if provider == "claude":
        return {}
    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("Error: --provider openrouter needs OPENROUTER_API_KEY, in the environment or in .env.")
    return {"ANTHROPIC_BASE_URL": "https://openrouter.ai/api", "ANTHROPIC_AUTH_TOKEN": key, "ANTHROPIC_API_KEY": ""}


class AgentError(RuntimeError):
    """An agent session failed or produced no reply; the phase is abandoned and can be rerun."""


# ---------------------------------------------------------------------------------------------
# Project state: everything is derived from files, so runs are resumable.


@dataclass
class Phase:
    kind: str  # "meeting", "research" or "done"
    number: int  # meeting number, or the number of the brief the research week will end with


def init_project(project: Path) -> None:
    """Copy missing template files into the project. Never overwrites, so it is safe on every run."""
    if not (project / "QUESTION.md").is_file():
        sys.exit(f"Error: {project}/QUESTION.md not found: write the question first.")
    template = CORE / "project-template"
    for src in template.rglob("*"):
        rel = src.relative_to(template)
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
    """Map meeting number -> path for files named MNN-<kind>.md (kind: brief, minutes, transcript)."""
    found = {}
    for p in (project / "meetings").glob(f"M*-{kind}.md"):
        m = re.fullmatch(rf"M(\d+)-{kind}\.md", p.name)
        if m:
            found[int(m.group(1))] = p
    return found


def supervisor_signed_off(transcript: Path) -> bool:
    """True if the supervisor said SIGN_OFF in this meeting.

    Uses the orchestrator-written transcript and only the supervisor's messages, so neither the
    student's minutes nor the student's own words can end the project.
    """
    if not transcript.exists():
        return False
    sections = transcript.read_text().split("\n## ")
    return any(s.startswith("Supervisor\n") and SIGN_OFF in s for s in sections)


def next_phase(project: Path) -> Phase:
    """Decide what to run next from meetings/ (mirrors the table in STUDENT.md)."""
    minutes = meeting_files(project, "minutes")
    briefs = meeting_files(project, "brief")
    if minutes:
        latest = max(minutes)
        if supervisor_signed_off(project / "meetings" / f"M{latest:02d}-transcript.md"):
            return Phase("done", latest)
    if 0 not in minutes:
        return Phase("meeting", 0)  # kickoff
    latest = max(minutes)
    pending = [n for n in briefs if n > latest]
    if pending:
        return Phase("meeting", min(pending))  # a brief is waiting for its meeting
    return Phase("research", latest + 1)  # the agreed actions are waiting to be done


# ---------------------------------------------------------------------------------------------
# Agents


def read(name: str) -> str:
    return (CORE / name).read_text()


class Agent:
    """One Claude Code session (via the Agent SDK). `send` returns the final text of the turn.

    Protocol files are read when the session starts, so edits to nightagent/*.md take effect from
    the next phase.
    """

    def __init__(self, role: str, project: Path, log: "RunLog", model: str | None, effort: str | None,
                 env: dict[str, str] | None = None):
        self.role, self.project, self.log = role, project, log
        self.model, self.effort, self.env = model, effort, env or {}
        self.client = None
        self.session_cost = 0.0  # running total reported by the SDK; used to log per-turn cost

    def options(self):
        from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

        # Both agents work in the project folder, ignore local Claude Code config and run under the
        # sandbox and permission policy above (see docstring).
        common = dict(cwd=str(self.project), setting_sources=[], model=self.model, effort=self.effort, env=self.env,
                      sandbox=SANDBOX, settings=json.dumps({"permissions": PERMISSIONS}),
                      max_buffer_size=MAX_MESSAGE_BYTES)
        if self.role == "student":
            # Student: Claude Code's normal coding-agent prompt plus all three public protocols, so it
            # understands the whole process (including how the supervisor works), but not the persona.
            # It runs unattended in "dontAsk" mode: STUDENT_TOOLS are pre-approved, Bash runs in the
            # sandbox, and anything that would need a human's approval is denied. The Agent tool is
            # removed so it cannot simulate a supervisor, and a PreToolUse hook (guard_student) checks
            # every tool call.
            prompt = "\n\n".join([read("STUDENT.md"), read("MEETING.md"), read("SUPERVISOR.md")])
            return ClaudeAgentOptions(
                system_prompt={"type": "preset", "preset": "claude_code", "append": prompt},
                permission_mode="dontAsk",
                allowed_tools=STUDENT_TOOLS,
                disallowed_tools=["Agent", "Task"],
                hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[self.guard_student])]},
                **common,
            )
        # Supervisor: a plain system prompt (protocol + meeting agenda + private persona) and read-only
        # tools. "dontAsk" denies anything not in allowed_tools instead of waiting for a human.
        prompt = "\n\n".join([read("SUPERVISOR.md"), read("MEETING.md"), PERSONA.read_text()])
        return ClaudeAgentOptions(
            system_prompt=prompt,
            tools=["Read", "Glob", "Grep"],
            allowed_tools=["Read", "Glob", "Grep"],
            permission_mode="dontAsk",
            **common,
        )

    async def guard_student(self, hook_input: dict[str, Any], tool_use_id: str | None, context: Any) -> dict[str, Any]:
        """PreToolUse hook for the student: deny tool calls that break the rules, and log them.

        - Any tool call whose arguments name the persona file is denied (Read, Grep, Bash `cat`, ...).
          This is best-effort: a shell glob that never spells the name would get past it.
        - File-tool writes (Write/Edit/...) outside the project folder are denied. Shell commands are
          also stopped by the sandbox (SANDBOX), which confines Bash writes to the project folder.
        """
        tool, args = hook_input["tool_name"], hook_input["tool_input"]
        reason = None
        if PERSONA.stem in json.dumps(args):
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
        from claude_agent_sdk import ClaudeSDKClient, ClaudeSDKError

        self.client = ClaudeSDKClient(self.options())
        try:
            await self.client.connect()
        except ClaudeSDKError as e:
            raise AgentError(f"{self.role} session failed to start: {short(str(e), 300)}") from e

    async def send(self, text: str) -> str:
        """Send one message and run the agent's turn (it may use many tools); return its final text.

        Tool calls and text are printed as they happen so the human can follow the run. Raises
        AgentError if the turn failed, ended without text or broke the SDK connection, so that an error
        is never relayed to the other agent as if it were a message and the phase stops cleanly.
        """
        from claude_agent_sdk import ClaudeSDKError

        try:
            return await self._send(text)
        except ClaudeSDKError as e:
            raise AgentError(f"{self.role} turn failed in the SDK: {short(str(e), 300)}") from e

    async def _send(self, text: str) -> str:
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

        await self.client.query(text)
        result, failed = "", False
        async for msg in self.client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, ToolUseBlock):
                        print(f"    [{self.role}] {block.name} {short(block.input)}")
                    elif isinstance(block, TextBlock) and block.text.strip():
                        print(f"    [{self.role}] {short(block.text)}")
            elif isinstance(msg, ResultMessage):
                result, failed = (msg.result or "").strip(), msg.is_error
                total = msg.total_cost_usd or 0.0
                self.log.event("turn", role=self.role, session=msg.session_id,
                               cost_usd=round(total - self.session_cost, 4), session_cost_usd=round(total, 4),
                               turns=msg.num_turns, error=msg.is_error)
                self.session_cost = total
        if failed or not result:
            raise AgentError(f"{self.role} turn {'failed' if failed else 'ended with no reply'}: {short(result, 300)}")
        return result

    async def close(self) -> None:
        if self.client:
            await self.client.disconnect()


class FakeAgent:
    """Stand-in for Agent in --dry-run: writes the files a real agent would, without API calls."""

    def __init__(self, role: str, project: Path, log: "RunLog", *_: Any):
        self.role, self.project, self.log, self.turns, self.meeting = role, project, log, 0, 0

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def send(self, text: str) -> str:
        self.turns += 1
        self.log.event("turn", role=self.role, session="dry-run", cost_usd=0.0, turns=1, error=False)
        if self.role == "supervisor":  # gives feedback, then agrees; signs off at the third meeting
            if self.turns == 1:
                self.meeting = int(re.search(r"Meeting M(\d+)", text).group(1))
                return "Feedback: show me the figures."
            return f"Agreed. {SIGN_OFF}." if self.meeting >= 2 else "Agreed."
        m = re.search(r"Phase: (research|minutes) M(\d+)", text)
        if m:
            name = "brief" if m.group(1) == "research" else "minutes"
            (self.project / "meetings" / f"M{int(m.group(2)):02d}-{name}.md").write_text(f"# {name} (dry run)\n")
            return f"{name} written."
        if "Agreed" in text:
            return f"Thanks.\n{END_MARKER}"
        return "Here is my update." if self.turns == 1 else "Proposed actions: make the figures. Agreed?"


# ---------------------------------------------------------------------------------------------
# Phases


class RunLog:
    """Append-only JSONL log of the run in meetings/harness-log.jsonl: phases, per-turn cost, blocked calls."""

    def __init__(self, project: Path):
        self.path = project / "meetings" / "harness-log.jsonl"

    def event(self, kind: str, **data: Any) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"), "event": kind, **data}) + "\n")


def short(x: Any, n: int = 100) -> str:
    """One-line, truncated rendering of text or tool input, for console output."""
    s = x if isinstance(x, str) else json.dumps(x)
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


async def run_meeting(project: Path, n: int, make_agent, log: RunLog, max_messages: int) -> None:
    """Relay a meeting between a fresh student session and a fresh supervisor session.

    The transcript is (re)started here, so an interrupted meeting is simply rerun from the beginning.
    The student opens and decides when the meeting ends (END_MARKER); the supervisor only replies.
    After the meeting, the same student session (which still has the conversation in context) writes
    the minutes, ACTIONS.md and memory.
    """
    mid = f"M{n:02d}"
    transcript = project / "meetings" / f"{mid}-transcript.md"
    transcript.write_text(f"# {mid} transcript\n\n_Written by the NightAgent orchestrator: every message, verbatim._\n")

    def record(speaker: str, text: str) -> None:
        with transcript.open("a") as f:
            f.write(f"\n## {speaker}\n\n{text}\n")
        print(f"  {speaker}: {short(text, 300)}")

    kind = "kickoff meeting" if n == 0 else "supervision meeting"
    student, supervisor = make_agent("student"), make_agent("supervisor")
    try:
        await student.start()
        await supervisor.start()
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
            # Safety limit against a runaway conversation, not a research limit; the minutes still get written.
            log.event("meeting_cut_off", meeting=mid, max_messages=max_messages)
            print(f"  Meeting {mid} hit the {max_messages}-message safety limit.")
        await student.send(
            f"Phase: minutes {mid}. The meeting is over; the orchestrator saved the verbatim transcript at "
            f"{transcript.relative_to(project)}. Now write meetings/{mid}-minutes.md, update ACTIONS.md and memory/ "
            f"(and QUESTION.md clarifications after the kickoff), as MEETING.md describes. If the supervisor said "
            f"\"{SIGN_OFF}\", say so in the minutes.")
    finally:
        await student.close()
        await supervisor.close()


async def run_research(project: Path, n: int, make_agent) -> None:
    """One research week: a fresh student session works through ACTIONS.md and ends by writing the brief."""
    student = make_agent("student")
    try:
        await student.start()
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
    ap.add_argument("--provider", default="claude", choices=sorted(DEFAULT_MODELS),
                    help="who serves the model: your Claude login/ANTHROPIC_API_KEY (default), or OpenRouter "
                         "(needs OPENROUTER_API_KEY in the environment or .env)")
    ap.add_argument("--model", help="model for both agents (default depends on --provider)")
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--max-meeting-messages", type=int, default=20,
                    help="safety limit on student replies per meeting (guards against a runaway loop)")
    args = ap.parse_args()

    project = args.project.resolve()
    init_project(project)
    log = RunLog(project)
    agent_cls = FakeAgent if args.dry_run else Agent
    model = args.model or DEFAULT_MODELS[args.provider]
    env = {} if args.dry_run else provider_env(args.provider)
    log.event("run_start", provider=args.provider, model=model, effort=args.effort, dry_run=args.dry_run)

    def make_agent(role: str):
        return agent_cls(role, project, log, model, args.effort, env)

    while True:
        phase = next_phase(project)
        if phase.kind == "done":
            print("Project signed off.")
            return
        mid = f"M{phase.number:02d}"
        print(f"== meeting {mid}" if phase.kind == "meeting" else f"== research week → {mid} brief")
        log.event("phase_start", phase=phase.kind, number=phase.number)
        try:
            if phase.kind == "meeting":
                await run_meeting(project, phase.number, make_agent, log, args.max_meeting_messages)
            else:
                await run_research(project, phase.number, make_agent)
        except AgentError as e:
            log.event("phase_failed", phase=phase.kind, number=phase.number, error=str(e))
            sys.exit(f"Stopping: {e}\nRun the same command again to retry this phase.")
        # Each phase must leave its output file; otherwise the next phase would be wrong.
        expected = project / "meetings" / f"{mid}-{'minutes' if phase.kind == 'meeting' else 'brief'}.md"
        if not expected.exists():
            sys.exit(f"Stopping: the student did not write {expected.name}. Run the same command again to retry.")
        log.event("phase_end", phase=phase.kind, number=phase.number)
        if not args.all:
            return


if __name__ == "__main__":
    asyncio.run(main())
