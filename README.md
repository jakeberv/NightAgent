# NightAgent

NightAgent is a friendly AI apprentice that learns from our interactions and puts that learning into action.

## What we are building

A supervised research apprentice for scientists. A supervisor sets the research direction, reviews results, and gives feedback; NightAgent performs analyses with tools and carries confirmed lessons into later work. Learning changes its stored context, not its model weights. In the current prototype the supervisor is itself an agent: the scientist writes the research question, and the supervisor's values are defined in a private persona.

The workshop goal is to build a small, inspectable prototype and evaluate two things separately: whether it becomes a better research student, and whether its research produces useful, supported scientific insights.

## How it works

1. **Supervision meeting:** present results, receive feedback, clarify ambiguity, and agree on the next actions.
2. **Research cycle:** choose approved analyses, run tools within limits, save reproducible results, and return for supervision.
3. **Persistent memory:** retain confirmed lessons with their source and scope, so corrections influence later meetings and analyses.

After feedback, the student extracts the actions and lessons and checks each for unclear meaning, unclear scope, or conflicting instructions. It asks batched clarification questions until the actions are clear, leaves unresolved items pending, and executes only agreed actions. This is an ambiguity check, not calibrated uncertainty about scientific truth.

## Minimal prototype

Following [autoresearch](https://github.com/karpathy/autoresearch), agent behaviour is defined in plain-language protocols, and Claude Code does the work. A small Python orchestrator ([nightagent/run.py](nightagent/run.py), using the Claude Agent SDK) runs a **student** and a **supervisor** as separate Claude Code sessions and relays the supervision meetings between them. The human only writes the question and starts the run. Memory is markdown files in the project folder.

### Repository layout

This repository defines the agents and how they work. It does not store project work: the only project content kept here is each example project's starting `QUESTION.md` (enforced by `.gitignore`).

- [nightagent/](nightagent/): the NightAgent application: the agents' protocols and the orchestrator that runs them. See its [README](nightagent/README.md).
  - [STUDENT.md](nightagent/STUDENT.md): how the student works: phases, research-week procedure, night science principles, memory and reproducibility rules, the living paper.
  - [MEETING.md](nightagent/MEETING.md): the meeting protocol: brief → present → feedback → clarification → agreed actions (a few days of student effort) → minutes and memory. Ends with a final meeting where the supervisor reviews the report.
  - [SUPERVISOR.md](nightagent/SUPERVISOR.md): the rules every supervisor follows: agrees a few days of work, confirms actions and lessons, reviews the final report, signs off. Both agents read it, so the student understands the whole process.
  - [REVIEWER.md](nightagent/REVIEWER.md): the independent reviewer that assesses a finished project: the hidden task metric, the science, the quality of the interaction, and observations.
  - [personas/](nightagent/personas/): the private personas: the supervisor's research values (the same for every supervisor; the student has to learn them through meetings), four supervision styles and four student personalities, which make up four relationship models (hands-off, pastoral, directive, collaborative).
  - [run.py](nightagent/run.py): the orchestrator. It runs the student and supervisor as separate Claude Code sessions, relays meetings between them and writes the transcripts.
  - [experiment.py](nightagent/experiment.py): runs every relationship model several times on one research question and reports the metrics per seed and per relationship.
  - [project-template/](nightagent/project-template/): everything a project starts with. `QUESTION.md` is the blank question for the human, written in the supervisor's voice (the supervisor treats it as its own); the rest is the skeleton the agents work in (`ACTIONS.md`, `memory/`, `meetings/`, `experiments/`, `tools/`, `REPORT.md`).
- [example-projects/](example-projects/): research questions, each a `QUESTION.md` plus a `hidden-question-metrics.md` that only the reviewer sees. [mnist/](example-projects/mnist/): "What is the best way to classify MNIST handwritten digits, and why do different models perform differently on it?" [magic/](example-projects/magic/): gamma vs hadron classification on the MAGIC telescope data, and why.

### Running a project

```bash
python3 -m venv nightagent/.venv && nightagent/.venv/bin/pip install -r nightagent/requirements.txt
```

To compare the four supervisor-student relationships, with 4 repeats each, on one research question:

```bash
nightagent/.venv/bin/python nightagent/experiment.py example-projects/magic --seeds 4
```

Each run goes from the kickoff meeting to sign-off (or a meeting limit), then an independent reviewer scores it; `runs/magic-<date>/results.md` reports every seed and the mean ± std per relationship. For a new question, create `example-projects/<name>/` with a filled-in copy of `nightagent/project-template/QUESTION.md` and a `hidden-question-metrics.md`. To run a single project phase by phase, use `run.py` with `--relationship`. Details, options, budget and the safety notes are in the [nightagent README](nightagent/README.md).

### How the loop works

The outer loop is supervision meetings, where the supervisor steers. The inner loop is research between meetings, where the student works alone. Each phase is a fresh session, so the project files are the only memory; only the supervisor knows its persona.

```
SETUP (human, once per research question)
  mkdir example-projects/<name>; write QUESTION.md in the supervisor's voice
      (question, context, what "best" means, constraints); optional data/code
  write hidden-question-metrics.md: the task metric only the reviewer sees
  run nightagent/experiment.py on that folder (or run.py on a copy of QUESTION.md)

EACH RUN (orchestrator)
  copy any missing template files into the project (never overwrites)
  decide the next phase from meetings/:
      supervisor said "Signed off" → stop
      no M00 minutes             → MEETING (kickoff)
      brief newer than minutes   → MEETING
      otherwise                  → RESEARCH

MEETING Mnn (fresh student session ↔ fresh supervisor session, relayed verbatim)
  student:    presents brief (kickoff: reframes question, asks about constraints, proposes plan)
  supervisor: believes it wrote QUESTION.md and holds the student to it;
              reads brief + earlier minutes; spot-checks evidence in the project folder;
              gives feedback shaped by its private persona;
              sets a few days of human-student effort
  repeat until clear:
    student:    batched clarification questions + candidate lessons
                ("should I remember you value X?") + restated actions
    supervisor: answers; "Agreed" or amends
  student ends with END MEETING
  orchestrator: has written meetings/MNN-transcript.md verbatim
  student:    writes minutes, ACTIONS.md (agreed only),
              memory (confirmed only; unresolved → pending.md)

RESEARCH (fresh student session, no overall time limit)
  agreed actions → goals with done-criteria
  explore first: alternative framings, methods from other fields, web search
  repeat until goals are done, or blocked, or a result changes the plan:
    experiment: prediction → runtime pilot (≤ 3 min per run) → run →
                results + figures → compare with prediction
    reusable code → tools/; update REPORT.md
  write brief (action status, key results, surprises, interpretation, options, questions)

ENDING
  supervisor judges the question answered well enough → "write it up"
  student finishes REPORT.md as a paper → final MEETING:
    supervisor reviews like a paper reviewer → student revises → … → "Signed off"
  (or the orchestrator stops the research after --max-meetings meetings)
  independent REVIEWER (fresh session, took no part) reads everything:
    hidden task metric, science, quality of interaction, observations → review/
```

Learning shows up in three places:

- The supervisor's preferences are in its private persona (figures, seeds, controlled comparisons, ablations, cross-field links), the same in every relationship model. The student discovers them only through feedback, delivered in the style of its supervisor.
- Memory holds only lessons the supervisor has confirmed, and the student rereads it at the start of every phase.
- The orchestrator's verbatim transcripts show whether the student starts acting on those preferences without being told again.

The proof of concept is the record in the project's `meetings/` (briefs, transcripts and minutes: results, feedback, Q&A, agreed actions), the memory files showing what the student learned about its supervisor, and the final `REPORT.md`, written like a short paper.

## Original workshop plan

The plan the team proposed in [SPEC.md](SPEC.md). The prototype above departs from it in places: Claude Code's own tools instead of four prewritten tools, markdown memory instead of JSON, and a supervisor agent instead of a human. The evaluation ideas still apply.

- Start with one scientist, one project, one model, a CLI, and editable JSON memory.
- Provide four prewritten tools: `inspect_project`, `run_analysis`, `read_results`, and `save_report`.
- Combine Tutorial 1's tool loop and traces with Tutorial 2's persistent memory and independent evaluation.
- Compare memory off, unconditional memory updates, and checked memory updates on six two-meeting cases with two repeats per condition.
- Score student behavior and scientific outcomes separately, alongside cost and runtime.
- Demonstrate feedback, clarification, a confirmed memory update, and a fresh session that uses the lesson.

The scientific task, dataset, analysis script, and role owners are still open. Candidate tasks belong in the notes. Generated tools, web/GitHub automation, multi-agent coordination, and a graphical interface are deferred.

## Project documents and status

- [SPEC.md](SPEC.md): approximately 400-word workshop proposal; a draft, not an implemented system.
- [NOTES.md](NOTES.md): design rationale, evaluation details, candidate tasks, and open decisions.
- [Shared design document](https://docs.google.com/document/d/1tBVSIyVEs3PdngYK7uHr1yEs5l3R0f5kC1OOjMMFqqA/edit?tab=t.tbzfgy1tsr0z): collaborative spec draft.

Status as of 21 October 2026: orchestrator with student, supervisor and reviewer agents, four relationship models and an experiment runner (`nightagent/`) on branch `dev-ben2`. Real runs so far used the earlier single persona (MNIST to M02, MAGIC to M01); the relationship personas and the reviewer are tested only with `--dry-run`. Next: one real seed of each relationship on MAGIC, then the full 4 × 4 experiment.

## Name and guiding ideas

Inspired by [Night Science](https://night-science.org/): explore before judging, improve the question, connect across fields, balance openness with structure, and return to evidence. These are adapted design principles, not claims that the agent already implements them.

## Team 5

Josef Osumeje - josumeje@umich.edu

Ben Moseley

Jake Berv — jacob.berv@gmail.com

Guido Herrera-R - guidohero@hotmail.com

Weiwei Chen - chenww535@gmail.com
