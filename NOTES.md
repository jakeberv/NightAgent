# NightAgent — design notes

Updated: 19 October 2026. These notes preserve the discussion behind the short [draft spec](SPEC.md). Proposed settings and candidate tasks remain subject to team review; no implementation or evaluation has been completed.

## Core idea and scope

### Operational pilot audit — 20 October 2026

Reviewed `magic-pilot-20261020-164827`: 12 successful local fits in 266.896 seconds,
31 completed model calls, complete $0.950805 accounting. Best validation AUC
0.9326917831 was trial 6, tied by trial 9. All artifact hashes and 26 accepted
contracts verified; this was validation-only, without held-out scoring.

Found an execution/interpretation mismatch: trial 8 described all features but
sent integer `max_features=1`, which the saved RF estimator interpreted as one
candidate feature. The numeric enum had accepted both 1 and 1.0. New requests
use explicit `sqrt`, `log2`, or `all`; numeric spellings are rejected, and `all`
maps to float 1.0. Both adapters are version 2; the new MAGIC prepared directory
is `study-data/magic-profile-v2`, with identical split arrays and updated provenance.
Historical trials and their scores remain unmodified.

Two supervisor responses needed repairs solely for prose surrounding fenced JSON.
The additional calls consumed 12.831 seconds and $0.075930. Reviews now accept one
unambiguous wrapped JSON object locally, while malformed or multiple objects,
duplicate fields and invalid evidence still fail validation.

Agent interpretations overclaimed optimality, ceilings, invariance and causal
explanations. New `grounded_v1` reasoning applies a conservative lexical guard
after citation validation: recognizable assertions become cited measurements,
and affected lessons become inconclusive. Original responses and each replacement
remain in audit logs; feedback, lessons and dashboard prose receive grounded text.
This guard is not a semantic proof system. Explicit hypotheses and uncertainties
remain labeled as such; other uncaught interpretations still need review. Actual
fitted parameters now reach agents, including effective RF feature counts.
Reports separate this policy from historical runs. The next API pilot must verify
live response quality and overhead; offline replay does not establish either.

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

## Completed MAGIC run audit — 20 October 2026

Reviewed local `study-runs/magic-workshop-20261020-161817` after pushing the
Focus improvements (`3b2249c`). Sources: immutable events, summary, progress log,
saved model artifacts, and report accounting. Historical run files were not edited.

- The 300-second periodic-reflection run completed nine successful local trials
  with a four-core allocation cap. Supervisor reviews followed trials 3, 6 and 9;
  reflections completed after trials 1–8. The final reflection exhausted the deadline.
- Trial 1 reached validation ROC-AUC 0.931019. Trial 8 was best at 0.932815
  (accuracy 0.873028, macro-F1 0.856442), using histogram gradient boosting,
  standard preprocessing, learning rate 0.025, max_iter 400 and 31 leaves.
  Improvement over trial 1 was 0.001796 AUC. The 0.95 stretch was not reached.
  This single split/run cannot establish a superior interaction strategy or
  statistical significance. No held-out test evaluation was performed.
- All nine saved model SHA-256 hashes matched, and all 20 accepted decision,
  supervisor and reflection contracts passed measurement/citation checks.
  Researcher uptake records were four followed, two modified and three with no
  prior feedback. Literature was correctly unavailable in this condition.
- Local trial time totaled 19.049 seconds; API calls totaled 280.566 seconds.
  Researcher: 11 calls, 94.792 seconds, $0.300543. Supervisor: 10 calls,
  90.570 seconds, $0.424131. Reflection: 11 calls, 95.203 seconds, $0.287418 known.
  The report cost no API calls. CPU parallelism is not the bottleneck in this run.
- Five rejected contracts (four prose length violations and one JSON preamble)
  consumed 68.396 seconds and $0.219639 before repairs. A final repair started
  with about 0.39 seconds left, timed out, and correctly made the final cost/token
  accounting incomplete: $1.012092 is a known subtotal, not a final bill.
- The supervisor overestimated remaining capacity using fit time alone and an
  out-of-date time snapshot, despite only three trial slots remaining. It also
  overclaimed an optimum, significance, a ceiling and underfitting. Inspection
  of the saved models showed trial 8 stopped at 392/400 iterations and trial 9
  at 366/400, contradicting the explanation that trial 9 exhausted its limit.
  Citation validation verifies numbers, not the truth of interpretations.

Corrections: refresh time/trial budgets and observed API latency before every
attempt; use concise multi-field format errors and explicit character limits;
disable extra tools while repairing review/reflection output; add a frozen
one-second API-start buffer with a logged skip (zero disables it); expose actual
HGB iteration/early-stopping diagnostics; strengthen instructions about
uncertainty, tested configurations and current-split scope. These changes retain
review cadence and hard deadlines. They are verified offline; their effect on
live response quality and cost still requires a subsequent API pilot.

Verification: all 377 tests passed, including controlled-clock budget/repair
regressions and a real worker fit with held-out data removed. The memory-enabled
offline smoke passed all five schedules (20 local fits, zero invalid contracts,
10 HGB iteration records, and eight report figures). Independent code review
found no remaining issues after extending compact errors to researcher tool
arguments. Smoke artifacts: `study-runs/log-review-smoke-20261020`. No paid API
calls were made during this audit or verification.
