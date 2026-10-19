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

## Minimal prototype (Claude Code as the harness)

Following [autoresearch](https://github.com/karpathy/autoresearch), the prototype has no custom harness code: Claude Code is the harness, and behaviour is defined in plain-language protocols. Both the student and the supervisor are agents. The human only writes the question and starts the run. Memory is markdown files in the project folder.

### Repository layout

This repository defines the agents and how they work. It does not store project work: the only project content kept here is the starting `QUESTION.md` of each example project (enforced by `.gitignore`).

- [nightagent/](nightagent/): the NightAgent application.
  - [STUDENT.md](nightagent/STUDENT.md): how the student works: running the project, research-week procedure, night science principles, memory and reproducibility rules, the living paper.
  - [MEETING.md](nightagent/MEETING.md): meeting protocol between student and supervisor: brief → present → feedback → clarification → agreed actions (about a week of student effort) → verbatim transcript, minutes and memory. Ends with a final meeting where the supervisor reviews the report.
  - [SUPERVISOR.md](nightagent/SUPERVISOR.md): how the supervisor behaves: checks the evidence, gives concise feedback, confirms actions, reviews the final report, signs off. Both agents read it, so the student understands the whole process.
  - [supervisor-persona.md](nightagent/supervisor-persona.md): what the supervisor values as good research. **Private to the supervisor**: the student is denied access to it, so it has to learn these values through meetings. The same persona is used for every project.
  - [project-template/](nightagent/project-template/): everything a project starts with. `QUESTION.md` is the blank question for the human, written in the supervisor's voice (the supervisor treats it as its own). The rest is the skeleton the agents start from (`ACTIONS.md`, `memory/`, `meetings/`, `experiments/`, `tools/`, `REPORT.md`, `.claude/`).
  - [new_project.sh](nightagent/new_project.sh): initialises a project folder in place. It copies in the template (never overwriting the human's files), builds the `supervisor` subagent (`.claude/agents/supervisor.md`) from SUPERVISOR.md plus the private persona, and denies the student access to the persona.
- [example-projects/](example-projects/): example projects. [mnist/](example-projects/mnist/) is ready to start: "What is the best way to classify MNIST handwritten digits, and why do different models perform differently on it?"
- [CLAUDE.md](CLAUDE.md): tells a student agent opened in a new project folder to initialise it before starting. It sits at the root so that sessions in `example-projects/` load it.

### Running a project

The MNIST example is ready to start. For a new question, create `example-projects/<name>/` with a copy of `nightagent/project-template/QUESTION.md` and fill it in. You can also add starting data or code.

Open Claude Code in the project folder (e.g. `example-projects/mnist`) with no worktree. Auto mode avoids permission prompts during unattended work. There are no limits on meetings or compute, except that each experiment must run in 3 minutes or less. Then say:

- **"run the project"**: kickoff → research → meeting → … → final meeting, until the supervisor signs off; or
- **"next step"**: one phase at a time, so you can inspect each one.

On the first run, the student initialises the folder with `new_project.sh`. If its new supervisor agent doesn't load until the session restarts, the student asks you to open a new session in the folder and say "run the project" again; this happens at most once.

To stop, interrupt the session. To resume, open a new session in the project folder and say "run the project": the student works out where it left off from `meetings/`. To start over, delete everything in the project folder except `QUESTION.md`.

### How the loop works

The outer loop is supervision meetings, where the supervisor steers. The inner loop is research between meetings, where the student works alone. The supervisor is a separate agent with its own context; both agents can read every file in the project folder, but only the supervisor knows its persona.

```
SETUP (human, once per project)
  mkdir example-projects/<name>; write QUESTION.md in the supervisor's voice
      (question, context, what "best" means, constraints); optional data/code
  open Claude Code in that folder (no worktree, auto mode); say "run the project"

INITIALISE (student agent, first session only; from the root CLAUDE.md)
  if no .claude/agents/supervisor.md: run nightagent/new_project.sh on this folder
      → copies template skeleton (memory/, meetings/, experiments/, tools/, REPORT.md, …)
      → builds supervisor agent: SUPERVISOR.md (public) + supervisor-persona.md (private)
      → denies the student access to the persona
  if the supervisor agent isn't loaded yet: ask the human to reopen the session; stop

MAIN LOOP (student agent; knows STUDENT.md, MEETING.md and SUPERVISOR.md)
  repeat:
    read QUESTION.md, ACTIONS.md, memory/*, latest minutes, experiments index
    decide next step from meetings/:
      final minutes "Signed off" → stop
      no M00 minutes             → MEETING (kickoff)
      latest = brief             → MEETING
      latest = minutes           → RESEARCH

MEETING Mnn (student ↔ supervisor agent, no length limit)
  student:    presents brief (kickoff: reframes question, asks about constraints, proposes plan)
  supervisor: believes it wrote QUESTION.md and holds the student to it;
              reads brief + earlier minutes; spot-checks evidence in the project folder;
              gives feedback shaped by its private persona;
              sets ~1 week of human-student effort
  student:    extracts actions/lessons; checks meaning, scope, conflicts
  repeat until clear:
    student:    batched clarification questions + candidate lessons
                ("should I remember you value X?") + restated actions
    supervisor: answers; "Agreed" or amends
  student records: verbatim transcript, minutes, ACTIONS.md (agreed only),
                   memory (confirmed only; unresolved → pending.md)

RESEARCH (student alone, no overall time limit)
  agreed actions → goals with done-criteria
  explore first: alternative framings, methods from other fields, web search
  repeat until goals are done, or blocked, or a result changes the plan:
    experiment: prediction → runtime pilot (≤ 3 min per run) → run →
                results + figures → compare with prediction
    reusable code → tools/; update REPORT.md
  write brief (action status, key results, surprises, interpretation, options, questions)
  → MEETING

ENDING
  supervisor judges the question answered well enough (or agrees to the student's proposal)
      → "write it up"
  student finishes REPORT.md as a paper → final MEETING:
    repeat: supervisor reviews like a paper reviewer → student revises
    until "Signed off"
```

Learning shows up in three places:

- The supervisor's preferences are in its private persona (figures, seeds, controlled comparisons, ablations, cross-field links). The student discovers them only through feedback.
- Memory holds only lessons the supervisor has confirmed, and the student rereads it before every step.
- The meeting transcripts show whether the student starts acting on those preferences without being told again.

The proof of concept is the record in the project's `meetings/` (briefs, verbatim transcripts and minutes: results, feedback, Q&A, agreed actions), the memory files showing what the student learned about its supervisor, and the final `REPORT.md`, written like a short paper.

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

Status as of 19 October 2026: minimal Claude Code prototype with student and supervisor agents (`nightagent/`, MNIST example project) on branch `dev-ben`; not yet run; no evaluation results yet. Next, choose an accessible task and script, assign owners, and build the fixed baseline before adding the adaptive loop.

## Name and guiding ideas

Inspired by [Night Science](https://night-science.org/): explore before judging, improve the question, connect across fields, balance openness with structure, and return to evidence. These are adapted design principles, not claims that the agent already implements them.

## Team 5

Josef Osumeje - josumeje@umich.edu

Ben Moseley

Jake Berv — jacob.berv@gmail.com

Guido Herrera-R - guidohero@hotmail.com

Weiwei Chen - chenww535@gmail.com
