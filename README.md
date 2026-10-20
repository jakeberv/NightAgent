# NightAgent

NightAgent is a friendly AI apprentice that learns from our interactions and puts that learning into action.

## What we are building

A supervised research apprentice for scientists. The scientist sets the research direction, reviews results, and gives feedback; NightAgent performs bounded analyses with tools and carries confirmed lessons into later work. Learning changes its stored context, not its model weights.

The workshop goal is to build a small, inspectable prototype and evaluate two things separately: whether it becomes a better research student, and whether its research produces useful, supported scientific insights.

## How it works

1. **Supervision meeting:** present results, receive feedback, clarify ambiguity, and agree on the next actions.
2. **Research cycle:** choose approved analyses, run tools within limits, save reproducible results, and return for supervision.
3. **Persistent memory:** retain confirmed lessons with their source and scope, so corrections influence later meetings and analyses.

After feedback, extract at most three actions or lessons. Check each for unclear meaning, unclear scope, or conflicting instructions. Ask at most one consolidated clarification question per meeting; leave unresolved items pending and execute only agreed actions. This is an ambiguity check, not calibrated uncertainty about scientific truth.

## Minimal prototype

Following [autoresearch](https://github.com/karpathy/autoresearch), agent behaviour is defined in plain-language protocols, and Claude Code does the work. A small Python orchestrator ([prototype/run.py](prototype/run.py), using the Claude Agent SDK) runs a **student** and a **supervisor** as separate Claude Code sessions and relays the supervision meetings between them. The human only writes the question and starts the run. Memory is markdown files in the project folder.

### Repository layout

This repository defines the agents and how they work. It does not store project work: the only project content kept here is each example project's starting `QUESTION.md` (enforced by `.gitignore`).

- [nightagent/](nightagent/): how the agents behave.
  - [STUDENT.md](nightagent/STUDENT.md): how the student works: phases, research-week procedure, night science principles, memory and reproducibility rules, the living paper.
  - [MEETING.md](nightagent/MEETING.md): the meeting protocol: brief → present → feedback → clarification → agreed actions (about a week of student effort) → minutes and memory. Ends with a final meeting where the supervisor reviews the report.
  - [SUPERVISOR.md](nightagent/SUPERVISOR.md): how the supervisor behaves: checks the evidence, gives concise feedback, confirms actions, reviews the final report, signs off. Both agents read it, so the student understands the whole process.
  - [supervisor-persona.md](nightagent/supervisor-persona.md): what the supervisor values as good research. **Private to the supervisor**: the student is blocked from reading it, so it has to learn these values through meetings.
  - [project-template/](nightagent/project-template/): everything a project starts with. `QUESTION.md` is the blank question for the human, written in the supervisor's voice (the supervisor treats it as its own); the rest is the skeleton the agents work in (`ACTIONS.md`, `memory/`, `meetings/`, `experiments/`, `tools/`, `REPORT.md`).
- [prototype/](prototype/): the orchestrator that runs a project. See its [README](prototype/README.md).
- [example-projects/](example-projects/): example projects, each starting with just `QUESTION.md`. [mnist/](example-projects/mnist/): "What is the best way to classify MNIST handwritten digits, and why do different models perform differently on it?"

### Running a project

```bash
python3 -m venv prototype/.venv && prototype/.venv/bin/pip install -r prototype/requirements.txt
```

```bash
prototype/.venv/bin/python prototype/run.py example-projects/mnist
```

Each run executes the next phase (first the kickoff meeting) and stops; `--all` continues until the supervisor signs off. For a new question, create `example-projects/<name>/` with a filled-in copy of `nightagent/project-template/QUESTION.md`. Details, options and the safety notes are in the [prototype README](prototype/README.md).

### How the loop works

The outer loop is supervision meetings, where the supervisor steers. The inner loop is research between meetings, where the student works alone. Each phase is a fresh session, so the project files are the only memory; only the supervisor knows its persona.

```
SETUP (human, once per project)
  mkdir example-projects/<name>; write QUESTION.md in the supervisor's voice
      (question, context, what "best" means, constraints); optional data/code
  run prototype/run.py on that folder

EACH RUN (orchestrator)
  copy any missing template files into the project (never overwrites)
  decide the next phase from meetings/:
      final minutes "Signed off" → stop
      no M00 minutes             → MEETING (kickoff)
      brief newer than minutes   → MEETING
      otherwise                  → RESEARCH

MEETING Mnn (fresh student session ↔ fresh supervisor session, relayed verbatim)
  student:    presents brief (kickoff: reframes question, asks about constraints, proposes plan)
  supervisor: believes it wrote QUESTION.md and holds the student to it;
              reads brief + earlier minutes; spot-checks evidence in the project folder;
              gives feedback shaped by its private persona;
              sets ~1 week of human-student effort
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
```

Learning shows up in three places:

- The supervisor's preferences are in its private persona (figures, seeds, controlled comparisons, ablations, cross-field links). The student discovers them only through feedback.
- Memory holds only lessons the supervisor has confirmed, and the student rereads it at the start of every phase.
- The orchestrator's verbatim transcripts show whether the student starts acting on those preferences without being told again.

The proof of concept is the record in the project's `meetings/` (briefs, transcripts and minutes: results, feedback, Q&A, agreed actions), the memory files showing what the student learned about its supervisor, and the final `REPORT.md`, written like a short paper.

## Workshop scope and goals

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

Status as of 19 October 2026: orchestrator prototype with student and supervisor agents (`nightagent/`, `prototype/`, MNIST example project) on branch `dev-ben2`; kickoff run on MNIST; no evaluation results yet. Next, choose an accessible task and script, assign owners, and build the fixed baseline before adding the adaptive loop.

## Name and guiding ideas

Inspired by [Night Science](https://night-science.org/): explore before judging, improve the question, connect across fields, balance openness with structure, and return to evidence. These are adapted design principles, not claims that the agent already implements them.

## Team 5

Josef Osumeje - josumeje@umich.edu

Ben Moseley

Jake Berv — jacob.berv@gmail.com

Guido Herrera-R - guidohero@hotmail.com

Weiwei Chen - chenww535@gmail.com
