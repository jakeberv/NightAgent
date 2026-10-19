# NightAgent — design notes

Updated: 19 October 2026. These notes preserve the discussion behind the short [draft spec](SPEC.md). Proposed settings and candidate tasks remain subject to team review; no implementation or evaluation has been completed.

## Current design: autonomous researcher and supervisor

The user selected this architecture for the updated spec on 19 October 2026 and explicitly requested that the scientific task remain generic. The local SPEC.md and Google Docs draft now describe two sequential roles sharing one model and Python harness. Humans provide the initial objective, constraints, and budget; execution does not require supervision meetings or confirmation.

Researcher → approved experiment → fixed computed metrics → supervisor review → next experiment or stop. The review cites run IDs, records uncertainty, and proposes one next action. Replication consumes the same experiment budget. The harness enforces limits; neither role can change the evaluator or see final test outcomes during search. Preserve scoped evidence-linked lessons, while treating unsupported suggestions as hypotheses.

Retain four prewritten tools and the localhost report viewer. The CLI launches a run; the browser presents plots, metrics, experiment history, reviews, limitations, and final comparisons. Proposed caps per run are three research/review rounds, six analyses, 60 seconds per analysis, 15 model calls including both roles, and 30,000 total input/output tokens. Stop with recorded results when blocked or capped.

Compare fixed baseline, researcher alone, and researcher plus supervisor on six predefined cases with two repeats per condition. Match resources across agent conditions, reset memory between cases, and keep final tests independent of search. Evaluate process reliability and scientific outcomes separately. The supervisor's ratings do not establish success. The researcher-only condition receives the same measured results/history and can use its full budget without supervisor calls.

Task-specific metrics and pass/fail checks, dataset/script access, and owners remain open. MNIST and the tutorial simulator remain candidates only. The earlier human confirmation and ambiguity-count design is superseded; it is preserved below as discussion history. No implementation or evaluation has been run.

# Historical design discussion

The following sections record earlier proposals and rationale. Where they differ, the current design above and SPEC.md take precedence.

## Earlier core idea and scope

**Earlier direction:** the team initially proposed a human-supervised apprentice, then considered an autonomous experiment improver and an agent supervisor. The current spec now adopts the researcher–supervisor roles with the task left generic.

NightAgent is a research apprentice supervised by a scientist. Its outer loop is a meeting: report results → receive feedback → clarify → agree on actions. Its inner loop uses tools to carry out those actions and produce evidence, artifacts, and a report.

The harness manages memory, tool execution, validation, limits, and traces. The agent is the model plus that harness when the model chooses analyses and follow-ups. Memory is a persistent state that influences later behavior; this workshop prototype does not train model weights. Remembering feedback alone is not evidence of improvement.

Keep the first build small: one scientist/project/model, a CLI for feedback, a local web results viewer, four prewritten tools, and editable JSON memory. Reuse Tutorial 1's loop/traces and Tutorial 2's memory/evaluation ideas. Defer generated tools, web/GitHub automation, multi-agent coordination, and browser chat.

## Minimum build: student presentations in a browser

The user requested a web server so the student can show results to the supervisor. Recommended implementation: extend Tutorial 1's Python harness and OpenRouter adapter, with a small local report viewer. The runtime choice remains a recommendation; the browser presentation capability is requested scope.

| Component | Minimum responsibility |
| --- | --- |
| Supervision CLI | Show the report URL, accept feedback, clarify, and confirm actions. |
| Research loop | Load agreed goals and relevant memories, call the model, execute approved tools, and enforce limits. |
| Scientific tools | Inspect data, run approved analyses, read saved results, and save a report. |
| Feedback/memory | Check at most three lessons, retain unresolved items as pending, and store confirmed JSON memories. |
| Results viewer | Serve a generated HTML report and its plots/artifacts on localhost. |
| Evaluation runner | Replay meetings across memory conditions and produce separate student/science scorecards. |

Extend `save_report` to render structured findings into a fixed HTML template alongside the Markdown report. Include the research question, run ID and settings, plots and metrics, evidence-linked findings, limitations, and proposed next steps. Link to previous run reports for comparison. If MNIST is selected, candidate panels include sample images, class counts, a confusion matrix, and example errors; MNIST remains outside the spec.

Start one server through the harness, serve only the report/artifact directory, print its localhost URL, and stop it on exit. The viewer reads saved outputs; viewing or refreshing a page does not trigger an analysis or model call. A standard-library static HTTP server and generated HTML are sufficient for the proposed first version. Manual browser refresh is enough; feedback stays in the terminal. The agent supplies structured report content through `save_report`; it does not generate or manage a new web application each cycle.

Minimum demonstration: run an analysis → inspect the browser report → give terminal feedback → clarify and confirm a lesson → restart the agent → run again → compare reports and both evaluation scorecards. Opening a report is presentation, not evidence of scientific success. No server or implementation has been created yet.

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

## Proposed pivot: autonomous experiment improver

Following supervisor feedback, reconsidered the two tutorial decks, Milestone II requirements, and tutorial code. The written requirements emphasize accessible data, a runnable baseline, and automatically checkable outcomes; they do not explicitly prohibit human involvement. No replacement project has been selected yet.

Recommended smallest candidate: use Tutorial 2's existing synthetic simulator. The agent proposes an eight-action REST/STEADY/BOOST protocol, tests it through a bounded tool, reads measured outcomes, and chooses its next protocol. Give it a small fixed budget, initially six candidate protocols. This is an experiment-selection agent; it does not need an LLM call for every simulator step. It chooses protocols as structured data, with no generated executable code.

Three proposed tools: `test_protocol` returns replicated scores and a run ID; `read_history` retrieves recorded candidates/results; `save_report` creates the browser report. The harness fixes seed batches and budgets, saves results automatically, and runs final evaluation separately. Begin with experiment history as memory; distilled lessons across campaigns are an optional extension.

Evaluate the selected protocol on held-out seeds against fixed BOOST/REST alternation and random protocol search with the same candidate and simulation budgets. Repeat whole searches independently. Report held-out mean reward, variability, experiment count, model cost, and invalid calls. Keep the evaluator fixed and final test results out of the search loop. The tutorial simulator is synthetic; any improvement applies to that environment, and beating random search is an empirical question.

This combines Tutorial 1's tool loop/traces with Tutorial 2's experience-based decisions. It replaces supervision meetings, feedback interpretation, confirmation, and student grading with measured outcomes. Retain the local web report. An alternative is the same loop for a small MNIST classifier, selecting from bounded training configurations using validation scores and a final untouched test set; it adds dataset/training setup. No implementation has started, and SPEC.md remains unchanged pending team direction.

## Proposed autonomous researcher and supervisor roles

User direction: remove the human from the execution loop; an agent supervisor is a candidate replacement. Humans would define the initial task, allowed tools, evaluation criteria, and budget, then inspect the final report.

Recommended minimal design: two roles called sequentially from one Python harness, potentially using the same model through OpenRouter. The researcher proposes and runs a bounded experiment. A supervisor receives the objective, run records, measured validation results, and remaining budget; it returns a structured review citing run IDs, one next action, and a continue/stop recommendation. Avoid an open-ended conversation between agents.

A fixed Python evaluator computes metrics and validity checks. The supervisor can interpret evidence and suggest experiments, but cannot change the evaluator, invent measurements, or access final test outcomes during search. The harness enforces limits regardless of either agent's recommendation. If evidence is uncertain, the supervisor can request replication within the budget or report an inconclusive result.

Start memory with an append-only experiment/review log. Treat supervisor suggestions as hypotheses; record supported lessons with evidence rather than automatically promoting every critique to fact. Retain the browser report for plots, experiment history, review decisions, and final results.

Proposed demo cap: three research/review rounds, at most six experiments in total, plus an explicit model-call/token limit set before running. Compare a researcher-only loop with researcher-plus-supervisor under the same experiment and model-call/token budgets; include a simple fixed or random baseline. Judge final outcomes with held-out evaluation, not the supervisor's own ratings. This tests whether the extra role adds value. These are design proposals, not implemented behavior or a finalized replacement spec.

## Sources and inspiration

The proposed autonomous pivot follows the same broad pattern as [Karpathy's autoresearch](https://github.com/karpathy/autoresearch), which Tutorial 2 explicitly cites: propose a change, run a bounded experiment, evaluate, retain useful results, repeat. Autoresearch edits training code and evaluates short LLM training runs; our smaller proposal chooses structured simulator protocols or bounded classifier configurations. A possible project question is whether experiment history or distilled lessons improve search versus equal-budget random search. That is a hypothesis to evaluate, not an established advantage or a finalized pivot.

- [Shared team brainstorm](https://docs.google.com/document/d/1tBVSIyVEs3PdngYK7uHr1yEs5l3R0f5kC1OOjMMFqqA/edit?tab=t.0)
- [Tutorial 1](https://github.com/ioanazelko/AgenticAI2026_Tutorial-1)
- [Tutorial 2](https://github.com/Ameyapores/AgenticAI2026_Turorial-2)
- [Night Science workshop approach](https://night-science.org/home/learn/): explore before judging, reframe questions, connect across fields, balance openness with structure, and test against evidence. These are our adapted guiding principles.
