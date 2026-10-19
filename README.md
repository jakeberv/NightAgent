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

Following [autoresearch](https://github.com/karpathy/autoresearch), the prototype has no custom harness code: Claude Code is the harness, and behaviour is defined in plain-language protocols. Both the student and the supervisor are agents. The human only sets up the project and starts the run. Memory is markdown files in the project repo.

- [STUDENT.md](STUDENT.md): how the student works: running the project, research-week procedure, night science principles, memory and reproducibility rules, the living paper.
- [MEETING.md](MEETING.md): meeting protocol between student and supervisor agent: brief → present → feedback → clarification → agreed actions (about a week of student effort) → verbatim transcript, minutes and memory. Ends with a final meeting where the supervisor reviews the report.
- [SUPERVISOR.md](SUPERVISOR.md): how the supervisor agent behaves (checks the evidence, gives concise feedback, confirms actions, reviews the final report, signs off), plus its private persona: what it values as good research. The same supervisor is used for every project.
- [project-template/](project-template/): everything a project starts with. `QUESTION.md` is the blank question for the human to fill in, written in the supervisor's voice (the supervisor agent treats it as its own). The rest is the skeleton the agents start from (`ACTIONS.md`, `memory/`, `meetings/`, `experiments/`, `tools/`, `REPORT.md`, `.claude/`).
- [CLAUDE.md](CLAUDE.md): tells a student agent opened in a new project folder to initialise it with `new_project.sh` before starting.
- [new_project.sh](new_project.sh): initialises a project folder in place (the student agent runs it; you can also run it yourself). It adds the template skeleton around the human's files (never overwriting them), builds the `supervisor` subagent (`.claude/agents/supervisor.md`) from SUPERVISOR.md, and makes the folder its own git repository. The student is denied read access to the supervisor files, so it has to learn the supervisor's values through meetings.
- [projects/mnist/](projects/mnist/): a ready-to-start project containing only its `QUESTION.md`: "What is the best way to classify MNIST handwritten digits, and why do different models perform differently on it?"

This repository holds the general harness plus project folders in `projects/`, each holding only a `QUESTION.md` (and any starting data or code). When a project is started, its folder becomes its own git repository, and the student's work is committed only there, never to this repository.

The MNIST project is ready to start. For a new question, create `projects/<name>/` with a copy of `project-template/QUESTION.md` and fill it in.

To start a project, open Claude Code in its folder (e.g. `projects/mnist`) with no worktree. Auto mode avoids permission prompts during unattended work. There are no limits on meetings or compute, except that each experiment must run in 3 minutes or less. Then say:

- **"run the project"**: kickoff → research → meeting → … → final meeting, until the supervisor signs off; or
- **"next step"**: one phase at a time, so you can inspect each one.

On the first run, the student initialises the folder with `new_project.sh`. If its new supervisor agent doesn't load until the session restarts, the student asks you to open a new session in the folder and say "run the project" again; this happens at most once.

To stop, interrupt the session. To resume, open a new session in the project folder and say "run the project": the student works out where it left off from `meetings/`.

### How the loop works

The outer loop is supervision meetings, where the supervisor agent steers. The inner loop is research between meetings, where the student works alone.

```
SETUP (human, once per project)
  mkdir projects/<name>; write QUESTION.md in the supervisor's voice
      (question, context, what "best" means, constraints); optional data/code
  open Claude Code in projects/<name> (no worktree, auto mode); say "run the project"

INITIALISE (student agent, first session only; from the root CLAUDE.md)
  if no .claude/agents/supervisor.md: run new_project.sh on this folder
      → adds template skeleton (memory/, meetings/, experiments/, tools/, REPORT.md, …)
      → builds supervisor agent from SUPERVISOR.md (protocol + general private persona)
      → denies student read access to the supervisor files
      → git init + "Project setup" commit (the project is its own repo)
  if the supervisor agent isn't loaded yet: ask the human to reopen the session; stop

MAIN LOOP (student agent)
  repeat:
    read QUESTION.md, ACTIONS.md, memory/*, latest minutes, experiments index
    decide next step from meetings/:
      no M00 minutes             → MEETING (kickoff)
      latest = minutes           → RESEARCH
      latest = brief             → MEETING
      final minutes "Signed off" → stop

MEETING Mnn (student ↔ supervisor agent, no length limit)
  student:    presents brief (kickoff: reframes question, asks about constraints, proposes plan)
  supervisor: believes it wrote QUESTION.md and holds the student to it;
              reads brief + earlier minutes; spot-checks evidence in the repo;
              gives feedback shaped by its hidden preferences;
              sets ~1 week of human-student effort
  student:    extracts actions/lessons; checks meaning, scope, conflicts
  repeat until clear:
    student:    batched clarification questions + candidate lessons
                ("should I remember you value X?") + restated actions
    supervisor: answers; "Agreed" or amends
  student records: verbatim transcript, minutes, ACTIONS.md (agreed only),
                   memory (confirmed only; unresolved → pending.md); commit

RESEARCH (student alone, no overall time limit)
  agreed actions → goals with done-criteria
  explore first: alternative framings, methods from other fields, web search
  repeat until goals are done, or blocked, or a result changes the plan:
    experiment: prediction → runtime pilot (≤ 3 min per run) → run →
                results + figures → compare with prediction → commit
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

- The supervisor's preferences are hidden in its persona (figures, seeds, controlled comparisons, ablations, cross-field links). The student discovers them only through feedback.
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

Status as of 19 October 2026: minimal Claude Code prototype with student and supervisor agents (protocols, template, MNIST project) on branch `dev-ben`; not yet run; no evaluation results yet. Next, choose an accessible task and script, assign owners, and build the fixed baseline before adding the adaptive loop.

## Name and guiding ideas

Inspired by [Night Science](https://night-science.org/): explore before judging, improve the question, connect across fields, balance openness with structure, and return to evidence. These are adapted design principles, not claims that the agent already implements them.

## Team 5

Josef Osumeje - josumeje@umich.edu

Ben Moseley

Jake Berv — jacob.berv@gmail.com

Guido Herrera-R - guidohero@hotmail.com

Weiwei Chen - chenww535@gmail.com
