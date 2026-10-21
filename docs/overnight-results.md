# Overnight results — 21 October 2026

**The overnight suite produced useful evidence but failed acceptance.** All 15
attempts started from launch commit `621f225`: 13 stopped at the normal deadline
and two stopped early after model timeouts made cost accounting incomplete. The
original audit remains **FAIL: seven errors and 18 warnings**, with launcher exit
code 2. It must remain unchanged when reliability fixes are validated.

The saved suite is
`study-runs/fashion-five-arm-overnight-20261021-020151`. It began at 02:01 Toronto
time and completed evaluation/reporting at 03:11 on 21 October. The
[portable receipt](evidence/fashion-overnight-2026-10-21.json) records source
identities, input hashes, every attempt, score summaries and a valid local trace.
Full independent replay still requires the ignored journals and model artifacts.

## What completed

- **349 completed fits and 349 verified model artifacts.** No invalid decision
  was executed; accepted decisions and raw provider messages agree.
- **663 model calls: 661 successful and two timed out.** Successful saved messages
  and usage agree with all 661 raw provider records. No billing or token receipt
  exists for the two timeouts.
- **$22.444005 known cost is a lower bound**, not the final billed total.
- Search was frozen before held-out evaluation. **29 unique artifacts** were
  evaluated for **37 selection records**; reporting completed.
- The 12 memory-enabled runs all saved lessons and delivered them to a later
  researcher request. The three memory-off controls saved and delivered none.

## Descriptive scores, including the incomplete attempts

These are means of the best validation-selected model from **all three attempts
per arm**, including the two early seed-42 stops. They describe the saved run;
they are not an accepted equal-budget comparison or a ranking.

| Approach | Completed fits | Mean best validation accuracy | Mean selected held-out accuracy |
|---|---:|---:|---:|
| Researcher alone | 120 | 88.0222% | 86.8033% |
| Frequent supervision | 42 | 86.9778% | 86.0833% |
| Periodic supervision | 78 | 87.3778% | 86.6067% |
| Periodic supervision and reflection | 58 | 88.1778% | 86.8800% |
| Periodic supervision and reflection, memory off | 51 | 87.0444% | 86.3667% |

All four reported 95% paired intervals for validation-accuracy differences include
zero. There is no demonstrated winner. The apparent aggregate memory-on advantage
also includes a truncated memory-off attempt. On the two memory pairs that both
reached their normal deadline (seeds 43 and 44), memory-on minus memory-off was
**0 and −0.1667 percentage points on validation**, and **0 and −0.73 points on
held-out accuracy**. These two pairs do not establish a memory benefit or harm.

## Why acceptance failed

The seven errors have three underlying failure paths:

| Attempt | What happened | Original audit consequence |
|---|---|---|
| `r00-frequent`, seed 42 | Researcher call timed out after 60 seconds; stopped at 194.37 seconds with four fits | Unexpected stop, incomplete accounting and fewer than seven fits |
| `r00-periodic_reflection_no_memory`, seed 42 | Supervisor call timed out after 60 seconds; stopped at 189.17 seconds with six fits | Unexpected stop, incomplete accounting and fewer than seven fits |
| `r01-periodic_reflection`, seed 43 | Final supervisor lesson summary had 241 characters against a 240-character limit; its repair could not be admitted before the deadline | Unrepaired contract error; the invalid note was rejected |

The 18 warnings consist of **14 repaired contract violations**, the **two failed
calls**, and **two final interactions without a subsequent experiment**. The
repaired proposals were rejected until valid; they were not invalid fits. There
were also **86 equivalent experiment proposals** that reused saved evidence
without another fit. These are operational and context-efficiency issues that
must be addressed before another paid validation.

The [earlier revised preflight failure](revised-preflight-results.md) remains a
separate immutable result. Its solo-memory omission was corrected and passed a
[targeted revalidation](solo-memory-revalidation.md) before this overnight launch.
The overnight failure is not a recurrence of that omitted-memory behavior.

## What the memory evidence shows

Of 380 researcher requests in enabled runs, **360 contained saved notes** and
**177 contained lesson measurements older than the request's recent-trial
window**. In **19 executed decisions**, validated evidence cited an older
measurement available in those saved notes. Repair requests are included in the
request counts; the receipt states the counting method and per-run totals.

This establishes persistence, delivery and some citation of older measurements.
It does not isolate memory as the cause of an action or show an accuracy gain.
Model-written prose can still misrecall an older configuration. Prefer the
saved configuration, grounded metric and artifact hash over a narrative claim.

## A valid local mechanism trace

A manually selected trace in `r02-periodic_reflection` illustrates the intended
loop even though the complete suite failed audit. The receipt preserves its
measurements and lesson; the journal locations below are one-based line numbers.

1. **Review after trial 9, line 184:** the supervisor recommends raising CNN
   learning rate from 0.005 to 0.007 while holding the other settings fixed.
2. **Executed decision, line 193:** the researcher records `followed`, cites
   trial 9 and tests the suggested configuration as trial 10.
3. **Measured result, line 200:** validation accuracy falls from **87.0333% to
   86.6667%**, or **0.3667 percentage points**. Both use five epochs, batch size
   256, 16 channels, weight decay 0.001 and seed 44.
4. **Saved lesson, line 206:** `cnn_learning_rate_boost` is marked `inconclusive`
   and cites the actual measurements from trials 8, 9 and 10.
5. **Later researcher request, line 208:** the saved lesson is delivered in its
   context. Delivery is verified; an effect on the next choice is not claimed.

This is an example of retaining an inconclusive outcome, not proof that the
recommendation helped. It is a labeled manual trace, not an accepted export from
`study.demo`. See the [presentation walkthrough](../DEMO.md).

## Demo readiness and what needs rerunning

The saved [historical portable replay](evidence/fashion-demo/demo.md) is ready
for a mechanism presentation from a fresh clone, with its old memory policy
clearly labeled. The manual trace above adds real evidence from the current
memory-default mapping. A strict demo export must reject this failed overnight
suite. Do not relax the gate or overwrite its original audit to create a pass.
An honest recorded mechanism demo does not require another full paid comparison.

For new operational acceptance, first complete the reliability fixes, review and
CI, then plan a brief paid preflight using a fresh allowance/budget check. No paid
rerun was requested or launched in this correction pass. The refreshed allowance
covers a small operational preflight, but not another full matrix at the
observed $22.44 lower-bound cost.

The minimum missing historical coverage is the seed-42 frequent and memory-off
attempts; any unrepaired-contract acceptance issue must also be resolved. Such a
partial rerun would only fill historical gaps if the treatment and runtime
policy were unchanged. The proposed context and retry changes alter that policy,
so new attempts cannot be spliced into this old suite as an accepted five-arm
scientific result. A clean comparative claim about the corrected system needs a
**fresh five-arm, three-repeat suite from one frozen source**, followed by full
accounting, held-out selection and audit acceptance. A full rerun is optional for
the scoped mechanism demo and remains a separate spending decision.
