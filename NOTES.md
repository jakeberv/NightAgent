# NightAgent — design notes

Updated: 19 October 2026. These notes preserve the discussion behind the short [draft spec](SPEC.md). Proposed settings and candidate tasks remain subject to team review; no implementation or evaluation has been completed.

## Core idea and scope

NightAgent is a research apprentice supervised by a scientist. Its outer loop is a meeting: report results → receive feedback → clarify → agree on actions. Its inner loop uses tools to carry out those actions and produce evidence, artifacts, and a report.

The harness manages memory, tool execution, validation, limits, and traces. The agent is the model plus that harness when the model chooses analyses and follow-ups. Memory is a persistent state that influences later behavior; this workshop prototype does not train model weights. Remembering feedback alone is not evidence of improvement.

Keep the first build small: one scientist/project/model, a CLI, four prewritten tools, and editable JSON memory. Reuse Tutorial 1's loop/traces and Tutorial 2's memory/evaluation ideas. Defer generated tools, web/GitHub automation, multi-agent coordination, and a GUI.

## Feedback without an expanding supervision burden

Place one bounded interpretation check after feedback and before updating active memory or starting the next cycle:

1. Extract at most three scoped actions or lessons.
2. For each, count unresolved checks: unclear meaning, unclear scope, conflicting instructions (0–3).
3. Zero means ready for scientist confirmation. Above zero, ask at most one consolidated clarification question per meeting.
4. Keep unresolved items pending; execute only agreed actions. Store confirmed lessons with their source and scope, merge duplicates, and supersede outdated entries.

The count measures ambiguity, not calibrated confidence or scientific truth. Do not discard uncertain feedback: retain it pending clarification. Separate what the scientist wants from whether a scientific claim is supported. A remembered hypothesis stays a hypothesis; a rejected idea need not become a permanent ban.

## Two separate evaluation levels

### Student performance: outer supervision loop

Does the agent become a more capable, dependable student across meetings? Define trace-backed pass/fail criteria for task understanding, useful clarification, retaining corrections, completing agreed work or explaining a justified stop, appropriate initiative, honest limitations, and escalation when blocked.

Compare behavior before and after feedback. Report pass rates, incorrect memories, missed valid feedback, repeated mistakes, clarification burden, and supervisor interventions. Good performance includes judgment within the agreed scope, not obedience alone.

### Scientific outcomes: inner research loop

Check numerical correctness, provenance, reproducibility, and validity of comparisons. Require a finding, supporting artifact, limitations, and an implication or testable next step.

A scientist separately scores relevance, evidential support, and added insight beyond the fixed baseline: 0 absent, 1 partial, 2 strong. Define task-specific examples before testing; hide the agent variant when feasible. Useful negative results can count if they change understanding or rule out a possibility. Unsupported novelty does not count, and correct execution alone does not establish an interesting finding.

A good student may reach an inconclusive result. An interesting result does not excuse poor supervision behavior. Keep these scorecards separate.

### Comparison design

Use six scripted two-meeting cases spanning clear, ambiguous, and conflicting feedback, with two repeats for each of three conditions: memory off, unconditional updates, checked updates. Match model, tools, starting data, prior results, and budgets; use scripted supervisor responses. Reset memory between cases and keep evaluation answers out of agent context. Predefine criteria and report cost/runtime. These are proposed tests, not results.

## Candidate tasks — not selected

The user requested that the spec remain generic. Keep these examples in the notes until the team chooses a task.

- **MNIST classifier (user suggestion):** build a classifier. Example supervisory requests include dataset exploration and visualization of the data or results. The dataset split, classifier, and scientific insight criteria remain undecided. Classification performance and the quality of the apprentice's response to supervision would be separate outcomes.
- **Plant CO2 uptake (earlier assistant suggestion):** explore whether chilling responses differ by plant origin using the public R CO2 dataset. Account for repeated measurements and small group sizes; do not assume a particular result. No analysis has been performed.
- **Tutorial 2 simulator (earlier assistant suggestion):** reuse its existing data/tools and measurable outcomes to reduce setup work. This was not selected as the project task.

## Practical limits and milestones

Proposed limits per cycle: five model calls including feedback checks, two analyses, and 60 seconds per analysis. Return to the supervisor when blocked. Estimate evaluation spend from a pilot and the full cases × conditions × repeats workload; proposed total cap $5, subject to available credits.

Workshop deadlines, Ontario local time:

- Monday 19 October, 5 PM: approximately 400-word SPEC.md.
- Tuesday 20 October, 5 PM: fixed baseline, one approved analysis plus one model summary.
- Wednesday 21 October, 11 AM: evaluation script.
- Wednesday 21 October, 1 PM: demo script.

Main dependency: accessible data and an approved script. Proposed Tuesday-noon scope fallback: fixed baseline plus confirmed memory; a runnable dataset/script is still required.

## Open decisions and next steps

- Select the scientific question, accessible dataset, analysis script, and reference calculations.
- Assign owners for harness/memory, tools/data, and evaluation/demo.
- Define task-specific scientific criteria and scripted supervisor cases before evaluation.
- Build and verify the fixed baseline, then add bounded tool choice and persistent feedback memory.
- Pilot cost/runtime before running the comparison; demonstrate the memory change and both scorecards.

## Sources and inspiration

- [Shared team brainstorm](https://docs.google.com/document/d/1tBVSIyVEs3PdngYK7uHr1yEs5l3R0f5kC1OOjMMFqqA/edit?tab=t.0)
- [Tutorial 1](https://github.com/ioanazelko/AgenticAI2026_Tutorial-1)
- [Tutorial 2](https://github.com/Ameyapores/AgenticAI2026_Turorial-2)
- [Night Science workshop approach](https://night-science.org/home/learn/): explore before judging, reframe questions, connect across fields, balance openness with structure, and test against evidence. These are our adapted guiding principles.
