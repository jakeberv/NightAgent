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
- [project-template/](project-template/): the starting point of every project. `QUESTION.md` (question, context, constraints) is for the operator to fill in, written in the supervisor's voice: the supervisor agent treats it as its own. The rest is the skeleton the agents start from (`ACTIONS.md`, `memory/`, `meetings/`, `experiments/`, `tools/`, `REPORT.md`, `.claude/`).
- [cases/](cases/): one folder per research case, containing only its filled-in `QUESTION.md` (plus any starting data or code). [cases/mnist/](cases/mnist/) asks "What is the best way to classify MNIST handwritten digits?"
- [new_project.sh](new_project.sh): turns a case into a project. It builds the `supervisor` subagent (`.claude/agents/supervisor.md`) from SUPERVISOR.md. The student is denied read access to both, so it has to learn the supervisor's values through meetings.

This repository holds only the general harness and case definitions. Each project is its own git repository, created under `projects/` (gitignored here), and the student's work is committed only there.

To run a case:

```bash
./new_project.sh cases/mnist
```

This creates `projects/mnist/`. Open Claude Code in that folder with no worktree (its `CLAUDE.md` imports the protocols). Auto mode avoids permission prompts during unattended work. There are no limits on meetings or compute, except that each experiment must run in 3 minutes or less. Then say:

- **"run the project"**: kickoff → research → meeting → … → final meeting, until the supervisor signs off; or
- **"next step"**: one phase at a time, so you can inspect each one.

To stop, interrupt the session. To resume, open a new session in the project folder and say "run the project": the student works out where it left off from `meetings/`.

The proof of concept is the record in the project's `meetings/` (briefs, verbatim transcripts and minutes: results, feedback, Q&A, agreed actions), the memory files showing what the student learned about its supervisor, and the final `REPORT.md`, written like a short paper.

To add a case, copy `project-template/QUESTION.md` to `cases/<name>/QUESTION.md` and fill it in.

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

Status as of 19 October 2026: minimal Claude Code prototype with student and supervisor agents (protocols, template, MNIST case) on branch `dev-ben`; not yet run; no evaluation results yet. Next, choose an accessible task and script, assign owners, and build the fixed baseline before adding the adaptive loop.

## Name and guiding ideas

Inspired by [Night Science](https://night-science.org/): explore before judging, improve the question, connect across fields, balance openness with structure, and return to evidence. These are adapted design principles, not claims that the agent already implements them.

## Team 5

Josef Osumeje - josumeje@umich.edu

Ben Moseley

Jake Berv — jacob.berv@gmail.com

Guido Herrera-R - guidohero@hotmail.com

Weiwei Chen - chenww535@gmail.com
