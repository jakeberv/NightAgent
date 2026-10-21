# Conversational Claude SDK prototype

This application defines a research student, its supervisor and their open-ended meeting/research loop. It is launched with `nightagent/run.py`. The [controlled study](../study/README.md), launched with `python -m study`, has separate dependencies, frozen tools, budgets, evaluation and configuration presets. Use the [five-arm launch recipe](../docs/five-arm-overnight.md) for the current study demo.

| File | What it is |
|---|---|
| [STUDENT.md](STUDENT.md) | How the student works: phases, research-week procedure, night science principles, memory and reproducibility rules, the living paper |
| [MEETING.md](MEETING.md) | The supervision meeting protocol, including the final report review |
| [SUPERVISOR.md](SUPERVISOR.md) | How the supervisor behaves (public: both agents read it) |
| [supervisor-persona.md](supervisor-persona.md) | What the supervisor values (included only in the supervisor prompt) |
| [project-template/](project-template/) | The files every project starts with; `QUESTION.md` is the one the human fills in |
| [run.py](run.py) | The orchestrator |
| [requirements.txt](requirements.txt) | Its one dependency, the Claude Agent SDK |

`run.py` drives the **student and the supervisor as separate Claude Code sessions** through the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk), and runs the meetings between them. Each project is one folder, e.g. [`../example-projects/mnist/`](../example-projects/mnist/).

## Orchestration behavior and limits

- **Phases:** it decides the next phase from `meetings/` and runs it in a fresh session, so the project files are the agents' only memory between phases.
- **Separate agents and transcript:** the student and supervisor are separate sessions. The orchestrator records returned meeting text under role headings in `meetings/MNN-transcript.md`; student continuation messages have `END MEETING` markers removed. The transcript remains a mutable project file.
- **Persona:** only the supervisor prompt includes the persona. A best-effort hook rejects student tool arguments containing `supervisor-persona`; indirect shell access can bypass this filename check.
- **Read-only supervisor:** the supervisor has only Read, Grep and Glob.
- **Student permissions:** Agent and Task tools are disabled. The hook checks Write/Edit/MultiEdit/NotebookEdit target paths; shell commands and file reads are not confined to the project.
- **Local settings:** both sessions use `setting_sources=[]`, so local Claude Code settings are not automatically loaded.
- **Sign-off detection:** the orchestrator searches parsed Supervisor sections in the latest transcript for literal `Signed off` text. Quoted or negated phrases and injected Markdown headings can trigger this heuristic.
- **Errors and retries:** a failed or empty final reply stops the invocation before that reply is relayed. Already written files remain; the next invocation chooses a phase from file existence. Inspect partial minutes or briefs before retrying. Retrying a meeting restarts its transcript; copy it first if needed.
- **Run log:** `meetings/harness-log.jsonl` records phases, sessions, the cost of each turn, blocked tool calls and failures.

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
- `--provider` (`claude` or `openrouter`, see below), `--model` (default `claude-opus-5-5`, or OpenRouter's Opus alias with `--provider openrouter`), `--effort` (default `high`).
- `--max-meeting-messages` (default 20): a safety limit on student replies within one meeting, so a stuck conversation can't loop forever. It is not a research limit; hitting it is logged.

### Using OpenRouter instead of a Claude login

By default the agents use Claude Code's login (your Claude subscription) or `ANTHROPIC_API_KEY`. To bill an OpenRouter account instead, put your key in a `.env` file at the repository root (it is gitignored), or export `OPENROUTER_API_KEY` in your shell, and add `--provider openrouter`:

```
OPENROUTER_API_KEY=your-key-here
```

```bash
nightagent/.venv/bin/python nightagent/run.py example-projects/mnist --provider openrouter
```

This applies the settings from [OpenRouter's Claude Code guide](https://openrouter.ai/docs/guides/guides/claude-code-integration) to both agents only: `ANTHROPIC_BASE_URL=https://openrouter.ai/api`, the key in `ANTHROPIC_AUTH_TOKEN`, and an empty `ANTHROPIC_API_KEY`. Your normal Claude Code setup is not changed. The default model is OpenRouter's alias `~anthropic/claude-opus-latest[1m]`; pass `--model` with an OpenRouter model id to choose another. `meetings/harness-log.jsonl` records which provider and model each run used.

Caveats:
- **The key is visible to the agents' shell.** It is in the environment of both sessions, so a student command such as `env` would print it, and it would then appear in the session logs. Use a key with a spending limit.
- **Provider routing:** OpenRouter only guarantees Claude Code compatibility with Anthropic as the serving provider; its guide recommends making Anthropic the top-priority provider in your OpenRouter settings.
- **Costs:** the cost figures in the run log come from Claude Code's own estimate, not OpenRouter's billing; check OpenRouter's activity page for actual spend.

If a research phase stops, inspect its files before retrying; a partial brief can change which phase runs next.

**The student runs unattended with full permissions** (`bypassPermissions`) inside the project folder: it installs packages and runs code there. A hook blocks the checked file-tool writes outside the folder, but shell commands are not sandboxed. Run it on a machine where that is acceptable.

## How a run works

```
init:      copy missing project-template files into the project (never overwrites)
next phase (from meetings/):
  parsed sign-off text detected    → done
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
