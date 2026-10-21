"""NightAgent orchestrator: runs a student, a supervisor and a reviewer agent as separate Claude Code sessions.

Usage:
    python nightagent/run.py <project_dir> --relationship pastoral   # first run: choose the relationship
    python nightagent/run.py <project_dir>            # run the next phase (one meeting or one research week)
    python nightagent/run.py <project_dir> --all      # run phases until the project is reviewed
    python nightagent/run.py <project_dir> --dry-run  # exercise the loop with fake agents (no API calls)
    python nightagent/run.py <project_dir> --provider openrouter   # bill OpenRouter (key in .env or env)

The project folder needs a QUESTION.md. On first use, the rest of nightagent/project-template/ is
copied in. Protocols (STUDENT.md, MEETING.md, SUPERVISOR.md, REVIEWER.md) and the personas
(personas/) are read from this folder. To run many relationships and repeats, use experiment.py.

Design decisions:
- Two separate agents. The student and supervisor are independent Claude Code sessions (via the
  Claude Agent SDK). In a meeting this program relays each message verbatim between them and writes
  the transcript itself, so the record of what the supervisor said is not written by the student.
- A fresh session for every phase. No conversation context survives from one phase to the next, so
  the project files (memory/, minutes, ACTIONS.md, experiments/) are the agents' only memory. This
  makes the effect of the memory files testable.
- All state lives in the project folder, except the condition (below). The next phase is derived
  from the files in meetings/ and review/, so a run can be stopped at any time and resumed by running
  the same command again.
- Relationships. A relationship pairs a supervision style (personas/supervisors/) with a student
  personality (personas/students/); --supervisor and --student can also be chosen separately. Every
  supervisor has the same private research values (personas/supervisor-values.md), so conditions
  differ only in style.
- The condition is recorded next to the project, not inside it (.<project>.nightagent.json), so the
  agents never see which relationship they are in. It is fixed on the first run.
- The end: when the supervisor signs off, or after --max-meetings meetings without sign-off, an
  independent reviewer agent assesses the project (REVIEWER.md) against the hidden task metric of the
  research question (hidden-question-metrics.md, which neither agent sees) and writes review/.
- Each agent sees only its own persona. The student is never given the supervisor's, and a hook
  blocks the student's tool calls that name private files.
- Isolation from the machine's own Claude Code configuration: setting_sources=[] means no agent loads
  CLAUDE.md files or settings.json, so behaviour depends only on the files in nightagent/.
- No extra restrictions and no sandbox: the student installs packages, downloads data and runs code
  without asking. All agents run in "dontAsk" mode with their tools pre-approved, so they never wait
  for a human; whatever Claude Code's built-in checks would still ask about (e.g. some writes outside
  the project folder) is denied, and logged as "denied" in the run log. The supervisor and the
  reviewer only have read tools, by design. Run it on a machine where that is acceptable.
- Accounting: meetings/harness-log.jsonl records every turn's cost, tokens and wall time per role;
  summarise() totals them, and review/metrics.json holds the totals once the project is reviewed.
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
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

CORE = Path(__file__).resolve().parent  # nightagent/: protocols, personas, template
PERSONAS = CORE / "personas"
VALUES = PERSONAS / "supervisor-values.md"
SUPERVISORS = sorted(p.stem for p in (PERSONAS / "supervisors").glob("*.md"))
STUDENTS = sorted(p.stem for p in (PERSONAS / "students").glob("*.md"))
# Each relationship model pairs a supervision style with the student personality it is known for.
RELATIONSHIPS = {
    "hands-off": ("hands-off", "self-starter"),  # laissez-faire: low structure, low support
    "pastoral": ("pastoral", "perfectionist"),  # low structure, high support
    "directive": ("directive", "pleaser"),  # high structure, low support
    "collaborative": ("collaborative", "pragmatist"),  # contractual: high structure, high support
}
HIDDEN_METRICS = "hidden-question-metrics.md"  # in a task folder next to QUESTION.md; reviewer only
PRIVATE_NAMES = ("personas", "supervisor-values", HIDDEN_METRICS, ".nightagent.json")  # student may not name
TEMPLATE_SKIP = {".gitkeep", ".DS_Store"}  # placeholder/OS files not copied into projects
END_MARKER = "END MEETING"  # the student ends a meeting with this line (see MEETING.md)
SIGN_OFF = "Signed off"  # the supervisor ends the project with this phrase (see SUPERVISOR.md)
DEFAULT_MODELS = {  # per provider; override with --model (OpenRouter uses its own model names)
    "claude": "claude-sonnet-5-5",
    "openrouter": "anthropic/claude-sonnet-5.5",  # a pinned version, so every run of an experiment uses the same model
}
# One message from Claude Code can carry a whole tool result (e.g. a figure the agent reads); the SDK's
# 1 MB default would end the phase with an error.
MAX_MESSAGE_BYTES = 64 * 1024 * 1024
# The student's tools, pre-approved; in "dontAsk" mode anything else is denied rather than prompted.
STUDENT_TOOLS = ["Bash", "Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep",
                 "WebSearch", "WebFetch", "TodoWrite"]
READ_TOOLS = ["Read", "Glob", "Grep"]  # the supervisor's and the reviewer's only tools
REVIEW_KEYS = ("task_metric", "science", "interaction", "observations")  # required in the reviewer's JSON


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
    kind: str  # "meeting", "research", "review" or "done"
    number: int  # meeting number, or the number of the brief the research week will end with


def init_project(project: Path) -> None:
    """Copy missing template files into the project. Never overwrites, so it is safe on every run."""
    if not (project / "QUESTION.md").is_file():
        sys.exit(f"Error: {project}/QUESTION.md not found: write the question first.")
    if (project / HIDDEN_METRICS).exists():
        sys.exit(f"Error: {project} holds {HIDDEN_METRICS}, so it is a task definition: the agents would be "
                 f"able to read the hidden metric. Run it with experiment.py, which copies only QUESTION.md "
                 f"into fresh run folders, or copy QUESTION.md into a new folder yourself.")
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


def condition_file(project: Path) -> Path:
    """Where the project's condition is recorded: next to the project, so no agent can read it."""
    return project.parent / f".{project.name}.nightagent.json"


def resolve_condition(project: Path, relationship: str | None, supervisor: str | None, student: str | None,
                      metrics: Path | None) -> dict[str, Any]:
    """Load the project's recorded condition, or record the one chosen on the command line.

    A condition is fixed once the project has started: asking for a different one is an error.
    """
    path = condition_file(project)
    if path.exists():
        saved = json.loads(path.read_text())
        asked = {"relationship": relationship, "supervisor": supervisor, "student": student,
                 "metrics": str(metrics.resolve()) if metrics else None}
        clash = {k: v for k, v in asked.items() if v is not None and v != saved.get(k)}
        if clash:
            sys.exit(f"Error: this project was started with {json.dumps(saved)}; it can't change to {json.dumps(clash)}.")
        return saved
    if relationship:
        default_supervisor, default_student = RELATIONSHIPS[relationship]
        supervisor, student = supervisor or default_supervisor, student or default_student
    if not (supervisor and student):
        sys.exit(f"Error: choose the relationship for this new project: --relationship {{{','.join(RELATIONSHIPS)}}}, "
                 f"or both --supervisor and --student.")
    # Named after the relationship model only if the pair is exactly that model's.
    label = next((name for name, pair in RELATIONSHIPS.items() if pair == (supervisor, student)), "custom")
    condition = {"relationship": label, "supervisor": supervisor, "student": student,
                 "metrics": str(metrics.resolve()) if metrics else None, "seed": None}
    path.write_text(json.dumps(condition, indent=2) + "\n")
    return condition


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


def ending(project: Path, max_meetings: int) -> str | None:
    """Why the research is over ("signed_off" or "meeting_limit"), or None if it isn't."""
    minutes = meeting_files(project, "minutes")
    if not minutes:
        return None
    if supervisor_signed_off(project / "meetings" / f"M{max(minutes):02d}-transcript.md"):
        return "signed_off"
    return "meeting_limit" if len(minutes) >= max_meetings else None


def next_phase(project: Path, max_meetings: int) -> Phase:
    """Decide what to run next from meetings/ and review/ (mirrors the table in STUDENT.md)."""
    minutes = meeting_files(project, "minutes")
    briefs = meeting_files(project, "brief")
    if ending(project, max_meetings):
        done = (project / "review" / "scores.json").exists()
        return Phase("done" if done else "review", max(minutes))
    if 0 not in minutes:
        return Phase("meeting", 0)  # kickoff
    latest = max(minutes)
    pending = [n for n in briefs if n > latest]
    if pending:
        return Phase("meeting", min(pending))  # a brief is waiting for its meeting
    return Phase("research", latest + 1)  # the agreed actions are waiting to be done


def summarise(project: Path) -> dict[str, Any]:
    """Totals from the run log: cost, tokens and wall time per role, plus meetings and research weeks.

    Turns from failed attempts count too: they were spent. Logs written before token accounting
    existed have no token fields; those turns count as zero tokens.
    """
    log = project / "meetings" / "harness-log.jsonl"
    events = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    roles: dict[str, dict[str, float]] = {}
    for e in events:
        if e["event"] == "turn":
            r = roles.setdefault(e["role"], {"cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "seconds": 0.0})
            for k in r:
                r[k] += e.get(k, 0) or 0
    research_agents = [r for role, r in roles.items() if role != "reviewer"]  # the project itself
    return {
        "roles": {role: {k: round(v, 4) for k, v in r.items()} for role, r in roles.items()},
        "meetings": len(meeting_files(project, "minutes")),
        "research_weeks": sum(e["event"] == "phase_end" and e["phase"] == "research" for e in events),
        "failed_phases": sum(e["event"] == "phase_failed" for e in events),
        "project_cost_usd": round(sum(r["cost_usd"] for r in research_agents), 4),
        "project_tokens": int(sum(r["input_tokens"] + r["output_tokens"] for r in research_agents)),
        "student_tokens": int(sum(roles.get("student", {}).get(k, 0) for k in ("input_tokens", "output_tokens"))),
        "student_hours": round(roles.get("student", {}).get("seconds", 0) / 3600, 3),
        "project_hours": round(sum(r["seconds"] for r in research_agents) / 3600, 3),
    }


# ---------------------------------------------------------------------------------------------
# Agents


def read(name: str) -> str:
    return (CORE / name).read_text()


def usage_totals(model_usage: dict[str, Any] | None) -> tuple[int, int]:
    """(input tokens including cache reads and writes, output tokens) summed over models."""
    usage = (model_usage or {}).values()
    inputs = sum(u.get("inputTokens", 0) + u.get("cacheReadInputTokens", 0) + u.get("cacheCreationInputTokens", 0)
                 for u in usage)
    return inputs, sum(u.get("outputTokens", 0) for u in usage)


class Agent:
    """One Claude Code session (via the Agent SDK). `send` returns the final text of the turn.

    Protocol and persona files are read when the session starts, so edits to them take effect from
    the next phase.
    """

    def __init__(self, role: str, project: Path, log: "RunLog", condition: dict[str, Any], model: str | None,
                 effort: str | None, env: dict[str, str] | None = None):
        self.role, self.project, self.log, self.condition = role, project, log, condition
        self.model, self.effort, self.env = model, effort, env or {}
        self.client = None
        # Running session totals reported by the SDK; each turn's share is logged as the difference.
        self.session_cost, self.session_tokens = 0.0, (0, 0)

    def options(self):
        from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

        # Every agent works in the project folder, ignores local Claude Code config, and runs unattended
        # in "dontAsk" mode: its tools are pre-approved, and anything that would still need a human's
        # approval is denied instead of waiting (see docstring).
        common = dict(cwd=str(self.project), setting_sources=[], model=self.model, effort=self.effort, env=self.env,
                      permission_mode="dontAsk", max_buffer_size=MAX_MESSAGE_BYTES)
        if self.role == "student":
            # Student: Claude Code's normal coding-agent prompt plus all three public protocols, so it
            # understands the whole process (including how the supervisor works), and its own persona,
            # but not the supervisor's. The Agent tool is removed so it cannot simulate a supervisor, and
            # the hide_private hook keeps the experiment's private files out of its tool calls.
            parts = [read("STUDENT.md"), read("MEETING.md"), read("SUPERVISOR.md")]
            parts.append((PERSONAS / "students" / f"{self.condition['student']}.md").read_text())
            return ClaudeAgentOptions(
                system_prompt={"type": "preset", "preset": "claude_code", "append": "\n\n".join(parts)},
                allowed_tools=STUDENT_TOOLS,
                disallowed_tools=["Agent", "Task"],
                hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[self.hide_private])]},
                **common,
            )
        if self.role == "supervisor":
            # Supervisor: a plain system prompt (protocol + meeting agenda + private values + style).
            parts = [read("SUPERVISOR.md"), read("MEETING.md"), VALUES.read_text(),
                     (PERSONAS / "supervisors" / f"{self.condition['supervisor']}.md").read_text()]
        else:
            # Reviewer: its protocol, the supervisor's values (to judge what the student learned) and
            # the hidden task metric; not the personas' styles, so it judges what it sees.
            metrics = self.condition.get("metrics")
            hidden = Path(metrics).read_text() if metrics else (
                "# Hidden task metric\n\nNone was defined for this project: set task_metric.value to null.")
            parts = [read("REVIEWER.md"), "# The supervisor's private research values\n\n" + VALUES.read_text(), hidden]
        # The supervisor and the reviewer only read: they judge the work, they don't do it.
        return ClaudeAgentOptions(system_prompt="\n\n".join(parts), tools=READ_TOOLS, allowed_tools=READ_TOOLS,
                                  **common)

    async def hide_private(self, hook_input: dict[str, Any], tool_use_id: str | None, context: Any) -> dict[str, Any]:
        """PreToolUse hook for the student: deny any tool call that names one of the experiment's private
        files (the personas, the hidden metric, the condition record), and log it. Part of the
        experiment's design, not a security boundary: it checks names, so a path the student never
        spells out is not seen.
        """
        tool, args = hook_input["tool_name"], hook_input["tool_input"]
        if not any(name in json.dumps(args) for name in PRIVATE_NAMES):
            return {}
        reason = "That file is private."
        self.log.event("blocked", role=self.role, tool=tool, reason=reason)
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": reason}}

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

        started = time.monotonic()
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
                cost, tokens = msg.total_cost_usd or 0.0, usage_totals(msg.model_usage)
                self.log.event("turn", role=self.role, session=msg.session_id,
                               cost_usd=round(cost - self.session_cost, 4), session_cost_usd=round(cost, 4),
                               input_tokens=tokens[0] - self.session_tokens[0],
                               output_tokens=tokens[1] - self.session_tokens[1],
                               seconds=round(time.monotonic() - started, 1), turns=msg.num_turns, error=msg.is_error)
                self.session_cost, self.session_tokens = cost, tokens
                for denial in msg.permission_denials or []:  # refused by Claude Code's built-in checks
                    self.log.event("denied", role=self.role, detail=short(denial, 300))
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
        self.log.event("turn", role=self.role, session="dry-run", cost_usd=0.01, input_tokens=1000,
                       output_tokens=100, seconds=1.0, turns=1, error=False)
        if self.role == "reviewer":
            scores = {"task_metric": {"name": "dry run", "value": 0.5, "source": None, "verified": False, "notes": ""},
                      "science": {"overall": 5}, "interaction": {"overall": 5, "values_learned": 2},
                      "observations": ["dry run"]}
            return f"## Summary\n\nDry run.\n\n```json\n{json.dumps(scores)}\n```"
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
    """Append-only JSONL log of the run in meetings/harness-log.jsonl: phases, per-turn usage, blocked calls."""

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


def parse_review(reply: str) -> dict[str, Any]:
    """The reviewer's scores: the last fenced json block of its reply, with the required keys."""
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", reply, re.DOTALL)
    try:
        scores = json.loads(blocks[-1])
    except (IndexError, json.JSONDecodeError) as e:
        raise AgentError(f"the reviewer's reply has no valid json scores block ({e})") from e
    missing = [k for k in REVIEW_KEYS if k not in scores]
    if missing:
        raise AgentError(f"the reviewer's scores lack {', '.join(missing)}")
    return scores


async def run_review(project: Path, make_agent, how: str, meetings: int) -> None:
    """The independent review: a fresh reviewer session reads the finished project and scores it.

    The orchestrator writes its reply to review/REVIEW.md and the parsed scores, with how the project
    ended and the run totals, to review/scores.json and review/metrics.json.
    """
    reason = ("the supervisor signed off in the last meeting" if how == "signed_off" else
              f"the orchestrator stopped it after {meetings} meetings without the supervisor signing off")
    reviewer = make_agent("reviewer")
    try:
        await reviewer.start()
        reply = await reviewer.send(
            f"The project in this folder is finished: {reason}. Review it as REVIEWER.md describes, "
            f"and end your reply with the json scores block.")
    finally:
        await reviewer.close()
    scores = parse_review(reply)
    out = project / "review"
    out.mkdir(exist_ok=True)
    (out / "REVIEW.md").write_text(f"# Independent review\n\n_Ended: {reason}._\n\n{reply}\n")
    (out / "scores.json").write_text(json.dumps({**scores, "ended": how, "meetings": meetings}, indent=2) + "\n")
    (out / "metrics.json").write_text(json.dumps(summarise(project), indent=2) + "\n")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path, help="project folder containing QUESTION.md")
    ap.add_argument("--relationship", choices=sorted(RELATIONSHIPS),
                    help="supervisor-student relationship model (needed on a project's first run)")
    ap.add_argument("--supervisor", choices=SUPERVISORS, help="supervision style, overriding the relationship's")
    ap.add_argument("--student", choices=STUDENTS, help="student personality, overriding the relationship's")
    ap.add_argument("--metrics", type=Path, help=f"the research question's {HIDDEN_METRICS}, for the reviewer")
    ap.add_argument("--all", action="store_true", help="run phases until the project is reviewed")
    ap.add_argument("--max-meetings", type=int, default=10,
                    help="stop the research after this many meetings without sign-off, and review it")
    ap.add_argument("--dry-run", action="store_true", help="use fake agents (no API calls)")
    ap.add_argument("--provider", default="claude", choices=sorted(DEFAULT_MODELS),
                    help="who serves the model: your Claude login/ANTHROPIC_API_KEY (default), or OpenRouter "
                         "(needs OPENROUTER_API_KEY in the environment or .env)")
    ap.add_argument("--model", help="model for all agents (default depends on --provider)")
    ap.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--max-meeting-messages", type=int, default=20,
                    help="safety limit on student replies per meeting (guards against a runaway loop)")
    args = ap.parse_args()

    project = args.project.resolve()
    init_project(project)
    condition = resolve_condition(project, args.relationship, args.supervisor, args.student, args.metrics)
    log = RunLog(project)
    agent_cls = FakeAgent if args.dry_run else Agent
    model = args.model or DEFAULT_MODELS[args.provider]
    env = {} if args.dry_run else provider_env(args.provider)
    # The condition is not logged here: the log is inside the project, where the agents could read it.
    log.event("run_start", provider=args.provider, model=model, effort=args.effort, dry_run=args.dry_run)

    def make_agent(role: str):
        return agent_cls(role, project, log, condition, model, args.effort, env)

    while True:
        phase = next_phase(project, args.max_meetings)
        if phase.kind == "done":
            print(f"Project finished and reviewed: see {project / 'review'}.")
            return
        mid = f"M{phase.number:02d}"
        print({"meeting": f"== meeting {mid}", "research": f"== research week → {mid} brief",
               "review": "== independent review"}[phase.kind])
        log.event("phase_start", phase=phase.kind, number=phase.number)
        try:
            if phase.kind == "meeting":
                await run_meeting(project, phase.number, make_agent, log, args.max_meeting_messages)
            elif phase.kind == "research":
                await run_research(project, phase.number, make_agent)
            else:
                how = ending(project, args.max_meetings)
                await run_review(project, make_agent, how, len(meeting_files(project, "minutes")))
        except AgentError as e:
            log.event("phase_failed", phase=phase.kind, number=phase.number, error=str(e))
            sys.exit(f"Stopping: {e}\nRun the same command again to retry this phase.")
        # Each phase must leave its output file; otherwise the next phase would be wrong.
        expected = {"meeting": project / "meetings" / f"{mid}-minutes.md",
                    "research": project / "meetings" / f"{mid}-brief.md",
                    "review": project / "review" / "scores.json"}[phase.kind]
        if not expected.exists():
            sys.exit(f"Stopping: {expected.name} was not written. Run the same command again to retry.")
        log.event("phase_end", phase=phase.kind, number=phase.number)
        if not args.all:
            return


if __name__ == "__main__":
    asyncio.run(main())
