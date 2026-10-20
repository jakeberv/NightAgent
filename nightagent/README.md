# NightAgent

The NightAgent application: the protocols that define a research student and its supervisor, and the orchestrator that runs them on a project.

| File | What it is |
|---|---|
| [STUDENT.md](STUDENT.md) | How the student works: phases, research-week procedure, night science principles, memory and reproducibility rules, the living paper |
| [MEETING.md](MEETING.md) | The supervision meeting protocol, including the final report review |
| [SUPERVISOR.md](SUPERVISOR.md) | How the supervisor behaves (public: both agents read it) |
| [supervisor-persona.md](supervisor-persona.md) | What the supervisor values (private: only the supervisor sees it) |
| [project-template/](project-template/) | The files every project starts with; `QUESTION.md` is the one the human fills in |
| [run.py](run.py) | The orchestrator |
| [requirements.txt](requirements.txt) | Its one dependency, the Claude Agent SDK |

`run.py` drives the **student and the supervisor as separate Claude Code sessions** through the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk), and runs the meetings between them. Each project is one folder, e.g. [`../example-projects/mnist/`](../example-projects/mnist/).

## What the orchestrator guarantees

- **Phases:** it decides the next phase from `meetings/` and runs it in a fresh session, so the project files are the agents' only memory between phases.
- **Separate agents:** the student and supervisor are separate sessions. The orchestrator relays each message verbatim and writes `meetings/MNN-transcript.md` itself, so the record of the meetings is neutral.
- **Persona privacy:** the persona goes only into the supervisor's instructions. A hook blocks any student tool call that mentions the persona file.
- **Read-only supervisor:** the supervisor has only Read, Grep and Glob.
- **Contained student:** a hook blocks the student from writing outside the project folder, and the student can't use the Agent tool, so it can't simulate a supervisor.
- **Isolation from local settings:** both sessions ignore `CLAUDE.md` files and Claude Code settings on the machine (`setting_sources=[]`).
- **Run log:** `meetings/harness-log.jsonl` records phases, sessions, the cost of each turn and any blocked tool calls.

## Setup

The Agent SDK ships its own Claude Code CLI, so a Python package is all you need (Python 3.10+). Run from the repository root:

```bash
python3 -m venv nightagent/.venv && nightagent/.venv/bin/pip install -r nightagent/requirements.txt
```

It authenticates the same way Claude Code does: an existing `claude` login (e.g. after installing Claude Code and running `claude` once), or `ANTHROPIC_API_KEY` in the environment. Check with:

```bash
nightagent/.venv/bin/python -c "import claude_agent_sdk, pathlib, subprocess; subprocess.run([str(pathlib.Path(claude_agent_sdk.__file__).parent / '_bundled' / 'claude'), 'auth', 'status'])"
```

## Running

The project folder only needs a `QUESTION.md`:

```bash
nightagent/.venv/bin/python nightagent/run.py example-projects/mnist
```

That runs the **next phase** only (first, the kickoff meeting) and stops, so you can read the transcript before continuing. Run it again for each next phase. Options:

- `--all`: keep going until the supervisor signs off.
- `--dry-run`: fake agents and no API calls; tests the loop and the files it writes.
- `--model` (default `claude-opus-5-5`), `--effort` (default `high`).
- `--max-meeting-messages` (default 20): a safety limit on student replies within one meeting, so a stuck conversation can't loop forever. It is not a research limit; hitting it is logged.

If a research phase stops without writing its brief, run the same command again: a fresh session picks up from the files.

**The student runs unattended with full permissions** (`bypassPermissions`) inside the project folder: it installs packages and runs code there. A hook stops it writing outside the folder, but shell commands are not sandboxed. Run it on a machine where that is acceptable.

## How a run works

```
init:      copy missing project-template files into the project (never overwrites)
next phase (from meetings/):
  minutes contain "Signed off"    → done
  no M00 minutes                  → meeting M00
  brief newer than latest minutes → meeting MNN
  otherwise                       → research week, ending with the next brief

meeting MNN:
  fresh student session + fresh supervisor session
  student: opening message ─► supervisor: reply ─► student ─► …   (relayed verbatim,
                                                                   appended to MNN-transcript.md)
  until the student ends a message with "END MEETING"
  student (same session): writes minutes, ACTIONS.md, memory/

research week:
  fresh student session: carries out the agreed actions (or the write-up), writes the next brief
```

## Status

Tested with `--dry-run` (the full loop to sign-off) and unit tests of the student's tool guard, and run for real on the MNIST kickoff meeting.
