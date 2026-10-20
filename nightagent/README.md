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
- **Persona privacy:** the persona goes only into the supervisor's instructions. Reads outside the project are blocked, and a hook also blocks any tool call that names the persona file.
- **Read-only supervisor:** the supervisor has only Read, Grep and Glob.
- **Contained agents:** both agents run under the repository owner's Claude Code permission policy, applied explicitly in `run.py` (`PERMISSIONS`): bypass-permissions mode is off and reads outside the project folder are blocked. Both run in `dontAsk` mode with a fixed tool list, so anything that would need approval is denied. A hook keeps file tools (Read, Write, Edit, Glob, Grep) inside the project, and refuses shell commands that name a path outside it other than system locations (`SYSTEM_PATHS`). The student can't use the Agent tool, so it can't simulate a supervisor.
- **Isolation from local settings:** both sessions ignore `CLAUDE.md` files and Claude Code settings on the machine (`setting_sources=[]`).
- **Neutral sign-off:** the project ends only when the supervisor's own words in the transcript contain "Signed off".
- **Errors stop the run:** if an agent's turn fails or produces no reply, the phase stops (nothing is relayed) and can be retried by running the command again.
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

If a research phase stops without writing its brief, run the same command again: a fresh session picks up from the files.

**The student runs unattended** inside the project folder, with network access: it installs packages, downloads data and runs code there without asking. There is no OS sandbox (Claude Code's sandbox refused the network hosts the student needs). The shell-command check reads the command text, so it is best-effort: a script the student writes and runs, or a path built at run time, can still reach outside the folder. Run it on a machine where that is acceptable.

## How a run works

```
init:      copy missing project-template files into the project (never overwrites)
next phase (from meetings/):
  supervisor said "Signed off"     → done
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
