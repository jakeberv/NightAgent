# NightAgent orchestrator prototype

An alternative way to run NightAgent. Instead of one interactive Claude Code session in which the student calls a `supervisor` subagent, a small Python program (`run.py`) drives the **student and the supervisor as separate Claude Code sessions** through the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk), and runs the meetings between them.

It reuses everything in [`../nightagent/`](../nightagent/): the protocols (`STUDENT.md`, `MEETING.md`, `SUPERVISOR.md`), the private persona (`supervisor-persona.md`) and `project-template/`. A short "harness note" is appended to each agent's instructions to replace the subagent mechanics. Projects are still one folder each, e.g. [`../example-projects/mnist/`](../example-projects/mnist/).

## What it changes

| | Interactive version (`nightagent/` + `CLAUDE.md`) | This orchestrator |
|---|---|---|
| Who drives | One student session; you say "run the project" | `run.py` decides the next phase from `meetings/` |
| Supervisor | Subagent the student calls | A separate session; the orchestrator relays messages |
| Context | One long student session | A fresh session per phase; files are the only memory |
| Meeting transcript | Written by the student | Written by the orchestrator, verbatim (a neutral record) |
| Persona privacy | Deny rules plus instructions | In the supervisor's system prompt only, and a hook blocks any student tool call that mentions the persona file |
| Supervisor's tools | Read, Grep, Glob | Read, Grep, Glob (read-only) |
| Project setup | Student runs `new_project.sh` | `run.py` copies in the template; no `CLAUDE.md` or `.claude/` needed |
| Run log | Claude Code's own session logs | Also `meetings/harness-log.jsonl`: phases, sessions, cost per turn, blocked tool calls |

## Setup

The Agent SDK ships its own Claude Code CLI, so a Python package is all you need (Python 3.10+):

```bash
python3 -m venv prototype/.venv && prototype/.venv/bin/pip install -r prototype/requirements.txt
```

It authenticates the same way Claude Code does: an existing `claude` login, or `ANTHROPIC_API_KEY` in the environment.

## Running

The project folder only needs a `QUESTION.md`. Run from the repository root:

```bash
prototype/.venv/bin/python prototype/run.py example-projects/mnist
```

That runs the **next phase** only (first, the kickoff meeting) and stops, so you can read `meetings/M00-transcript.md` before continuing. Run it again for the next phase. Options:

- `--all`: keep going until the supervisor signs off.
- `--dry-run`: fake agents and no API calls; tests the loop and the files it writes.
- `--model` (default `claude-opus-5-5`), `--effort` (default `high`).
- `--max-meeting-messages` (default 20): a safety limit on student replies within one meeting, so a stuck conversation can't loop forever. It is not a research limit; hitting it is logged.

**The student runs unattended with full permissions** (`bypassPermissions`) inside the project folder: it installs packages and runs code there. A hook stops it writing outside the project folder, but shell commands are not sandboxed. Run it on a machine where that is acceptable.

## How a run works

```
init:      copy missing nightagent/project-template files into the project (never overwrites)
next phase (from meetings/):
  minutes contain "Signed off"   → done
  no M00 minutes                 → meeting M00
  brief newer than latest minutes → meeting MNN
  otherwise                      → research week, ending with the next brief

meeting MNN:
  fresh student session + fresh supervisor session
  student: opening message ─► supervisor: reply ─► student ─► …   (relayed verbatim,
                                                                   appended to MNN-transcript.md)
  until the student ends a message with "END MEETING"
  student (same session): writes minutes, ACTIONS.md, memory/

research week:
  fresh student session: carries out the agreed actions (or the write-up), writes the next brief
```

The protocols themselves (meeting agenda, memory rules, the 3-minute limit per experiment, the final report review) are unchanged: see the main [README](../README.md).

## Status

Tested with `--dry-run` (the full loop to sign-off, phase detection, transcripts, the run log) and by unit-testing the student's tool guard. **Not yet run against the real API.**
