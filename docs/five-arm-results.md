# Completed five-arm comparison — 21 October 2026

The corrected Fashion-MNIST study completed all fifteen ten-minute attempts on
main commit `473271b86c75911f5d3b85c00d6ac3ba7e60bebf`. Search froze before held-out
scoring. Report generation and the independent audit finished at 13:35 Toronto.
This is the accepted comparison; the [earlier failed overnight study](overnight-results.md)
and interrupted replacement remain historical evidence.

## Results and limits

All five arms used matched training seeds 42–44, the same frozen data split and
search bounds, $5 per-run guards, two concurrent runs sharing four CPU cores,
and one MPS fit at a time. Lesson memory started empty in each run and was off
only in the explicit control. Memory-off still received recent trial history
and supervisor/reflection feedback; it was not a stateless agent.

The table reports means over all three seeds. Target attainment refers to
validation accuracy; held-out scores belong to the validation-selected models.

| Arm | Validation accuracy | Held-out accuracy | Fits/run | Model cost/run | Tokens/run | Reached 88% validation |
|---|---:|---:|---:|---:|---:|---:|
| Researcher alone | 86.66% | 85.79% | 30.0 | $1.46 | 401,920 | 1/3 |
| Frequent supervision | 88.07% | 87.12% | 20.0 | $1.61 | 433,322 | 2/3 |
| Periodic supervision | 88.31% | 87.17% | 26.3 | $1.56 | 429,354 | 3/3 |
| Periodic + reflection + memory | 88.22% | 87.12% | 20.3 | $1.91 | 529,109 | 3/3 |
| Periodic + reflection, memory off | 87.09% | 86.26% | 18.0 | $1.55 | 425,906 | 1/3 |

The four declared contrasts, with held-out differences in percentage points
for seeds 42, 43 and 44 respectively, were:

- Frequent versus solo: **−0.73, +2.39, +2.32**. Supervision avoided the weaker
  random-forest search paths in two seeds; solo won the other. More fits alone
  did not guarantee a better result.
- Periodic versus frequent: **0, +0.01, +0.16**. Similar accuracy with about 32%
  more fits and slightly lower mean cost gives periodic supervision a useful
  balance in this sample.
- Adding reflection to periodic: **0, 0, −0.16**. Average cost increased 22%,
  with six fewer fits per run and no final-accuracy gain.
- Memory on versus off with reflection: **+2.03, −0.52, +1.06**. The mean gain
  was 0.86 points, but the mixed three-seed result does not prove a general benefit.

All fifteen attempts reached 85% validation accuracy, ten reached 88%, and none
reached 90%. No selected-best held-out score reached 88% (maximum 87.96%).
These are exploratory results on one task and one split. Fixed training seeds
do not make model generation or shared-resource timing deterministic. Do not
use the held-out results to select replacements or retune the frozen study.

## Acceptance and observable interactions

The saved audit passed with **zero errors and sixteen warnings**: fifteen
contract repairs and one final reflection rejected for seven citations where
six were allowed. Repair admission then refused another call at deadline;
that reflection was neither accepted nor delivered.

All 344 artifacts, 624 model calls, $24.268839 cost and 6,658,833 tokens reconcile.
There were no failed calls/fits or unknown charges. Forty frozen selections used
36 unique held-out cache entries. All twelve enabled runs saved and delivered
run-local lessons; the three controls wrote none. All 235 accepted advisor
candidates were novel when accepted; six completed recommendations were rejected.

A concrete trace in `r00-periodic_reflection/events.jsonl` follows advice at
lines 60/64 through decision 70, trial-4 measurement 77, lesson 83 and later
context 85. Increasing CNN batch size from 256 to 512 yielded 0.844 accuracy
versus trial 3's 0.860333; the later decision tried batch 128. The trace proves
delivery and an observable next action, not the causal truth of the lesson.

There were **29 skipped duplicate proposals**, costing $1.189641 in calls:
solo 23, frequent 0, periodic 4, reflection 0, memory-off 2. No duplicate was
trained. Twenty-eight proposals were followed by new fits; solo seed 42's final
duplicate was followed by normal deadline admission stop. The longest chain
was three; no attempt stopped for `no_progress`.

The interrupted earlier source had 35 duplicates in 231 researcher calls versus
29 in 374 now. Different protocols, seed coverage and completed exposure make
this descriptive, not a causal before/after improvement claim. Provider timeout
and unknown-billing recovery did not trigger live in the completed study.

## Offline follow-up

The follow-up preserves the original evidence and adds no paid study:

- Report timing lives in `report-accounting.json`; the report command no longer
  changes `postrun.json` after hashing it. Repeated report commands verify every
  recorded input digest. The original stale digest concerned timing only.
- Cardinality feedback names the field, permitted item count and received count
  without dumping the long array. Real rejected reflection fixtures exercise
  repair and truthful deadline abandonment without relaxing citation limits.
- Duplicate recovery shows recorded requests for the same model in full, using
  existing history. The prompt asks for an actual permitted difference and warns
  against revisiting another completed configuration. All 29 saved proposals
  replay through the production guard with scripted model/fit fixtures. This
  verifies feedback delivery and no duplicate training, not live duplicate reduction.
- Uptake labels explicitly say **researcher-reported**. Of 171 executed decisions
  saying `followed`, 126 exactly matched the latest supervisor configuration;
  the other 45 followed already-fulfilled advice, often choosing reflection
  instead. Stated uptake is not literal configuration compliance or causality.

The original local evidence is under
`study-runs/fashion-five-arm-20261021-121920`; derived final and independent
reviews are in `monitor/`. The corrected report is in `monitor/reviewed-report/`.
Raw runs and credential-bearing logs stay untracked. A full paid rerun is not
justified for these reporting/feedback fixes. Any future claim that the prompt
reduces live duplicates needs a separately budgeted, narrowly targeted check.

Verification on the follow-up branch: **1,163 offline regression tests passed
in 207.17 seconds**. Independent code review found no blockers. Rendering the
accepted suite to the separate destination produced 48/48 matching input hashes;
the original audit, reports and raw evidence hashes remained unchanged.
