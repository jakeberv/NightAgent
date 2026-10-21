# Current workshop protocol

Updated 21 October 2026. This document and [the one-page specification](../SPEC.md)
describe the implemented workshop experiment. The [launch recipe](five-arm-overnight.md)
and frozen JSON/profile supply executable settings. Earlier MAGIC/MNIST AUC and
literature comparisons are development history, not additional arms in this study.
See [project goals](project-goals.md) for the apprentice vision and
[workshop milestones](workshop-milestones.md) for requirement coverage and gaps.

The memory-default implementation was merged into main in
[PR 14](https://github.com/jakeberv/NightAgent/pull/14) at `3b4a385`. The subsequent
[contract fix](https://github.com/jakeberv/NightAgent/pull/15) passed offline checks
and [targeted solo revalidation](solo-memory-revalidation.md). Integration and
launch gates are tracked in the [readiness ledger](workshop-readiness.md).
At that revalidation stage, the full comparison and held-out scoring were pending.

The subsequent [overnight comparison](overnight-results.md) completed 349 fits
and post-search held-out scoring, but failed acceptance after two timeout stops
and a rejected terminal review. Current reliability fixes and review/CI results
are recorded in [readiness](workshop-readiness.md). The new execution registry
and timeout policy change operational context: old and corrected attempts must
not be spliced into a new accepted comparison. A recorded mechanism demo remains
available without a claim of strategy superiority.

## Research question and tutorial components

Does structured supervision improve a research apprentice's choice of experiments
enough to justify the communication time and API cost? Inspect question framing,
recommendations, researcher responses, configuration changes, measured results and
the scope of retained lessons. Outcomes alone cannot explain the mechanism.
Tutorial 1's tools and traces and Tutorial 2's reflection and memory provide two
workshop components. Reliability checks and explicit role coordination also draw
on Tutorial 4. MCP integration and reinforcement learning are optional extensions.

## Frozen scientific comparison

Use Fashion-MNIST only. The prepared, fingerprinted partitions contain 12,000
training and 3,000 validation images from the official training set; preserve the
official test set for final confirmation. Maximize validation accuracy, record
macro-F1 and macro one-vs-rest ROC-AUC, and retain the 85%, 88% and 90% targets.
The bounded search includes logistic regression, random forest, torch MLP and CNN.
Fit preprocessing on training data only. The agent receives validation evidence,
never test labels or held-out results during search.

Five arms have three matched repeats with training seeds 42–44:

1. `researcher_alone`: ordinary researcher planning and run-local lesson memory; no supervisor.
2. `frequent`: Night Science supervision after each attempt, with memory.
3. `periodic`: Night Science supervision after every three attempts, with memory.
4. `periodic_reflection`: periodic supervision plus researcher reflection after each attempt, with memory.
5. `periodic_reflection_no_memory`: the same periodic supervision and reflection as arm four, with lesson memory disabled.

All supervised arms receive the same initial framing before their first fit.
All arms receive recent experiment history. The first four retain a separate
evidence-linked lesson register across the 12-trial history window; memory is a
standard apprentice capability, including in the researcher-alone arm. The
explicit fifth control has no lesson register or lesson updates. Lessons start
empty in every independent run and do not transfer between repeats. Literature tools are disabled.
At the first researcher decision with completed evidence and an empty enabled
register, require a cited, scoped observation note through `lesson_updates`.
The first decision without evidence and the memory-off control are exempt;
omission at an eligible decision receives bounded repair. The
[memory contract](memory-default.md) defines validation and scope.
Reviews stop when there is no time for another experiment. Count completed,
failed and timed-out attempts consistently for the schedule.

Use `anthropic/claude-sonnet-4.5` through OpenRouter's Anthropic provider,
temperature 0, maximum 2,048 output tokens and one retry. Each run has 600 seconds,
a 45-second fit timeout, 1,000-attempt safety cap and $5 API guard. Fifteen guards
sum to $75; they are not a billing ceiling because an in-flight call can overrun.
Unknown cost is not accepted as complete accounting. Share four CPU cores across
two concurrent runs and serialize MPS fits. Queue time consumes the allowance;
this measures the shared-machine policy, not isolated-compute efficiency.
Randomize run order with seed 2026. Reserve 1,200 seconds for evaluation/reporting
inside a two-hour suite deadline. Do not tune partitions, thresholds or settings
between arms after seeing outcomes.

## Baselines and evaluation cases

Run a fixed standard-scaled logistic classifier (`C=1`, `max_iter=300`, seed 42)
once on the same training/validation data as a task-difficulty anchor, outside all
five arms. It makes no model calls and receives no search budget. Researcher
alone is the matched adaptive baseline. Keep reference and search comparisons
distinct; one fixed fit is not an equal-effort estimate of agent benefit.

The fixed reference completed on 21 October in 4.74 seconds: 81.03% validation
accuracy, macro-F1 0.80904 and macro one-vs-rest ROC-AUC 0.97336. The
[verified reference receipt](fixed-reference.md) records its configuration and
provenance. No model calls or held-out scoring were required.

[Eight named acceptance cases](evaluation-cases.md) package deterministic pass/fail
checks for normal execution and important failures. Run
`python -m study.workshop_eval --output study-runs/workshop-evaluation`.
These cases meet the workshop's checkable-evaluation deliverable; the fifteen
scientific runs are one dataset × five treatments × three repeats, not fifteen
independent tasks. The full pytest suite remains the broader regression gate.

Compare four declared contrasts: frequent minus researcher-alone for supervision,
periodic minus frequent for cadence, periodic-reflection minus periodic for
reflection, and periodic-reflection minus periodic-reflection-no-memory for
memory. The first three hold memory on; the last is explicitly memory-on minus
memory-off. Report all matched pairs and nonattainment, completed validation quality,
time/cost to targets, total runtime/API cost, token accounting and failure rates.
After all searches freeze, score verified selected artifacts on held-out data
once per unique artifact. Do not feed those scores back into another search.
Inspect a small real-trace sample for advice uptake, changed behavior, correct
citations, uncertainty and lesson scope. Deterministic contracts check evidence
references; an LLM trace judge is not implemented. Three repeats and one task
support a demonstration, not general strategy rankings or cross-run learning.

## Demonstration and acceptance

Use [the demo script](../DEMO.md) to replay saved real-model evidence and show the
HTML comparison. Export a portable Markdown/JSON replay before presenting. Show
recommendation → decision/configuration → result → scoped lesson and subsequent
delivery. An unsuccessful comparison can still produce a useful, appropriately
limited lesson. A delivered lesson alone does not demonstrate benefit.

The [saved real preflight](targeted-preflight.md#historical-live-results--2026-10-20)
used the former policy: memory off in four arms and on only in its final arm.
Its 35 fits, 68 model calls, $1.665228 cost and 85.4%–87.5% best accuracies are
historical mechanism evidence, not validation of the revised memory-default
protocol. The [portable replay](evidence/fashion-demo/demo.md) remains a fallback.
Its memory arm reached 85% before its first lesson; that crossing is not evidence
of memory benefit. Retain historical-source and repaired-contract warnings.
The revised [bounded preflight](targeted-preflight.md) allows seven validation
fits in each of the five arms, with one seed, 300 seconds and a $2 API guard per
arm; it performs no held-out scoring. The [21 October paid run](revised-preflight-results.md)
completed all 35 fits and verified artifacts, with 65 real model calls,
429,259 tokens and $1.665021 cost. Its audit reported two errors from the
researcher-alone arm's missing lesson creation/delivery and resulting missing
final register, with no warnings. All seven solo decisions omitted optional
`lesson_updates`; the other four arms passed coverage checks. Offline checks
did not expose this live behavior. This failed acceptance result remains preserved.

The [contract correction and solo revalidation](solo-memory-revalidation.md)
added the first-eligible-note requirement and passed 961 regression tests. Only
the failed solo arm was rerun: seven fits and calls, $0.163809, three
lesson-update events for one lesson ID, and five later researcher contexts with
lessons. All seven artifacts verified and the audit passed with zero errors
and warnings. The first note preceded fit two. The other four arms were not
rerun under this source, so these separate receipts do not establish a combined
current-source five-arm pass or a causal memory benefit. Use the new solo cost
measurement in the provisional launch estimate.

Require successful launcher exit, complete accounting, verified artifacts,
fifteen completed runs, three pairs per contrast, required interaction/memory
coverage, completed held-out work and a passing independent `study audit`.
Investigate every warning. Do not automatically rerun a paid failure.
Recheck key allowance, current billing evidence and AC power immediately before
launch; apply the funding decision in the [readiness ledger](workshop-readiness.md).
Full account balance remains unavailable and has not been verified. Keep
credentials out of Git, documents and exported traces.
The repository maintainer coordinates integration; component-owner assignments
remain subject to team confirmation.

## Workshop milestones

See [the milestone checklist](workshop-milestones.md) for the official deadlines,
deliverables, evidence and remaining submission or ownership gaps. Available
artifacts do not prove submission or organizer acceptance. The repeated paid
comparison remains a separate launch decision.
