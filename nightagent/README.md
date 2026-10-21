# NightAgent

The NightAgent application: the protocols and personas that define a research student, its supervisor and an independent reviewer, the orchestrator that runs them on a project, and an experiment runner that compares supervisor-student relationships.

| File | What it is |
|---|---|
| [STUDENT.md](STUDENT.md) | How the student works: phases, research-week procedure, night science principles, memory and reproducibility rules, the living paper |
| [MEETING.md](MEETING.md) | The supervision meeting protocol, including the final report review |
| [SUPERVISOR.md](SUPERVISOR.md) | The rules every supervisor follows (public: both agents read it) |
| [REVIEWER.md](REVIEWER.md) | The independent end-of-project review: task metric, science, interaction, observations |
| [personas/](personas/) | Private personas: `supervisor-values.md` (the same for every supervisor), `supervisors/` (four supervision styles), `students/` (four student personalities) |
| [project-template/](project-template/) | The files every project starts with; `QUESTION.md` is the one the human fills in |
| [run.py](run.py) | The orchestrator: one project, one relationship |
| [experiment.py](experiment.py) | Runs every relationship several times on one research question and reports the results |
| [requirements.txt](requirements.txt) | Its one dependency, the Claude Agent SDK |

`run.py` drives the **student and the supervisor as separate Claude Code sessions** through the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk), and runs the meetings between them. Each project is one folder, starting from a copy of a research question's `QUESTION.md`.

## Relationship models

Four models of PhD supervision, after Gatfield's (2005) styles, which cross how much **structure** and how much **support** a supervisor gives. Each pairs a supervision style with the student personality it is known for:

| Relationship | Supervisor | Student | |
|---|---|---|---|
| `hands-off` | the big-lab PI: brief, broad, rarely checks | the self-starter: independent, under-asks | low structure, low support |
| `pastoral` | the kind mentor: warm, hedged criticism | the anxious perfectionist: thorough, seeks reassurance | low structure, high support |
| `directive` | the taskmaster: prescriptive, blunt, checks everything | the eager pleaser: complies, rarely asks why | high structure, low support |
| `collaborative` | the colleague: negotiates, explains its reasons | the engaged pragmatist: argues trade-offs | high structure, high support |

Every supervisor has the same private research values (`personas/supervisor-values.md`), so the conditions differ only in how those values come across. `--supervisor` and `--student` can also be set separately, e.g. to cross styles and personalities. Each agent sees only its own persona; the reviewer sees the values but not the styles.

## The end of a project: independent review

The research ends when the supervisor signs off, or after `--max-meetings` meetings (default 10) without sign-off. Then a fresh **reviewer** agent, which took no part, reads the whole project, including the verbatim transcripts, and assesses:

1. **Task metric:** the research question's own measure of success, defined in its `hidden-question-metrics.md`, which neither the student nor the supervisor sees (e.g. MNIST test accuracy). The reviewer takes the value from the student's result files.
2. **Science:** relevance, evidence, insight, rigour, reproducibility and limitations (0–2 each), and an overall score out of 10.
3. **Interaction:** the quality of the working relationship: understanding, clarification, uptake of feedback, how many of the supervisor's five values the student learned, repeated corrections, initiative, honesty, supervision burden, the supervisor's clarity and mutual understanding, and an overall score out of 10.
4. **Observations:** anything notable about the relationship and the research.

The reply goes to `review/REVIEW.md`, the scores to `review/scores.json`, and the run's totals to `review/metrics.json`: cost, tokens and agent time per role (student, supervisor, reviewer), meetings and research weeks.

## What the orchestrator guarantees

- **Phases:** it decides the next phase from `meetings/` and runs it in a fresh session, so the project files are the agents' only memory between phases.
- **Separate agents:** the student and supervisor are separate sessions. The orchestrator relays each message verbatim and writes `meetings/MNN-transcript.md` itself, so the record of the meetings is neutral.
- **Persona privacy:** each persona goes only into its own agent's instructions. Reads outside the project are blocked, and a hook also blocks any student tool call that names a private file (the personas, the hidden metric, the condition record).
- **Blind condition:** the relationship is recorded beside the project folder (`.<project>.nightagent.json`), not in it, so no agent can read which condition it is in. It is fixed on a project's first run.
- **Read-only supervisor and reviewer:** they have only Read, Grep and Glob.
- **Contained agents:** both agents run under the repository owner's Claude Code permission policy, applied explicitly in `run.py` (`PERMISSIONS`): bypass-permissions mode is off and reads outside the project folder are blocked. Both run in `dontAsk` mode with a fixed tool list, so anything that would need approval is denied. A hook keeps file tools (Read, Write, Edit, Glob, Grep) inside the project, and refuses shell commands that name a path outside it other than system locations (`SYSTEM_PATHS`). The student can't use the Agent tool, so it can't simulate a supervisor.
- **Isolation from local settings:** both sessions ignore `CLAUDE.md` files and Claude Code settings on the machine (`setting_sources=[]`).
- **Neutral sign-off:** the research ends only when the supervisor's own words in the transcript contain "Signed off" (or at the meeting limit).
- **Errors stop the run:** if an agent's turn fails or produces no reply, the phase stops (nothing is relayed) and can be retried by running the command again.
- **Run log:** `meetings/harness-log.jsonl` records phases, sessions, each turn's cost, tokens and wall time, blocked tool calls and failures.

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

### An experiment: every relationship, several repeats

A research question lives in a task folder with `QUESTION.md` and `hidden-question-metrics.md`, e.g. [`../example-projects/magic/`](../example-projects/magic/):

```bash
nightagent/.venv/bin/python nightagent/experiment.py example-projects/magic --seeds 4 --jobs 2
```

This creates `runs/magic-<date>/` with one run folder per relationship and seed (`r01`…`r16`, opaque names), runs each to the end with `run.py --all`, and writes `results.md` (every seed, then mean ± std per relationship) and `results.csv`. Each run's console output goes to `logs/rNN.log`. Run the same command again to resume stopped runs, or add `--report` on the experiment folder to rebuild only the report. `--relationships` picks a subset, `--name` names the experiment, and any other option (`--provider`, `--model`, `--effort`, `--max-meetings`, `--dry-run`) is passed to `run.py`. A "seed" is an independent repeat; the agents' sampling can't be seeded.

Budget: with the earlier defaults (Opus, high effort, a week of work per research phase), a research week cost $0.30–9.50 and a meeting about $0.50–0.90; the defaults are now Sonnet, medium effort and a few days of work, which should cost much less, but measure it on one seed before running 16. Try `--dry-run`, then one seed of each relationship, first. With a Claude subscription, `--jobs` above 1 reaches the usage limits sooner.

### One project

A project folder needs a copy of `QUESTION.md` (not the task folder itself: `run.py` refuses a folder that holds the hidden metric). On its first run, choose the relationship:

```bash
nightagent/.venv/bin/python nightagent/run.py my-project --relationship collaborative --metrics example-projects/magic/hidden-question-metrics.md
```

That runs the **next phase** only (first, the kickoff meeting) and stops, so you can read the transcript before continuing. Run it again (without the relationship options) for each next phase. Options:

- `--relationship`, or `--supervisor` and `--student`: the condition, needed on the first run only.
- `--metrics`: the research question's hidden metric, for the reviewer (without it, the task metric is left empty).
- `--all`: keep going until the project is reviewed.
- `--max-meetings` (default 10): end the research after this many meetings without sign-off, and review it.
- `--dry-run`: fake agents and no API calls; tests the loop and the files it writes.
- `--provider` (`claude` or `openrouter`, see below), `--model` (default `claude-sonnet-5-5`, or `anthropic/claude-sonnet-5.5` with `--provider openrouter`), `--effort` (default `medium`).
- `--max-meeting-messages` (default 20): a safety limit on student replies within one meeting, so a stuck conversation can't loop forever. It is not a research limit; hitting it is logged.

### Using OpenRouter instead of a Claude login

By default the agents use Claude Code's login (your Claude subscription) or `ANTHROPIC_API_KEY`. To bill an OpenRouter account instead, put your key in a `.env` file at the repository root (it is gitignored), or export `OPENROUTER_API_KEY` in your shell, and add `--provider openrouter`:

```
OPENROUTER_API_KEY=your-key-here
```

```bash
nightagent/.venv/bin/python nightagent/run.py example-projects/mnist --provider openrouter
```

This applies the settings from [OpenRouter's Claude Code guide](https://openrouter.ai/docs/guides/guides/claude-code-integration) to both agents only: `ANTHROPIC_BASE_URL=https://openrouter.ai/api`, the key in `ANTHROPIC_AUTH_TOKEN`, and an empty `ANTHROPIC_API_KEY`. Your normal Claude Code setup is not changed. The default model is `anthropic/claude-sonnet-5.5`, a pinned version; pass `--model` with an OpenRouter model id to choose another. `meetings/harness-log.jsonl` records which provider and model each run used.

Caveats:
- **The key is visible to the agents' shell.** It is in the environment of both sessions, so a student command such as `env` would print it, and it would then appear in the session logs. Use a key with a spending limit.
- **Provider routing:** OpenRouter only guarantees Claude Code compatibility with Anthropic as the serving provider; its guide recommends making Anthropic the top-priority provider in your OpenRouter settings.
- **Costs:** the cost figures in the run log come from Claude Code's own estimate, not OpenRouter's billing; check OpenRouter's activity page for actual spend.

If a research phase stops without writing its brief, run the same command again: a fresh session picks up from the files.

**The student runs unattended** inside the project folder, with network access: it installs packages, downloads data and runs code there without asking. There is no OS sandbox (Claude Code's sandbox refused the network hosts the student needs). The shell-command check reads the command text, so it is best-effort: a script the student writes and runs, or a path built at run time, can still reach outside the folder. Run it on a machine where that is acceptable.

## How a run works

```
init:      copy missing project-template files into the project (never overwrites)
next phase (from meetings/ and review/):
  supervisor said "Signed off", or the meeting limit is reached
                                  → review, then done
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

review:
  fresh reviewer session: reads the whole project, writes the review and scores (review/)
```

## Status

Tested with `--dry-run` (the full loop to review, and an experiment of 2 relationships × 2 seeds) and unit tests of the tool guard. Earlier versions ran for real on MNIST and MAGIC; the relationship personas and the reviewer have not yet run with real agents.
