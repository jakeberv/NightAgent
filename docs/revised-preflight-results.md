# Revised paid preflight — 21 October 2026

**Original decision: NO-GO.** The revised five-arm preflight completed all 35
fits, but failed the required researcher-alone memory coverage. Underlying account
funding was unverified. The audit criteria were not weakened, and no automatic
paid rerun or overnight launch was attempted at the time of this receipt.

The corrected contract subsequently passed a
[targeted paid solo revalidation](solo-memory-revalidation.md). The original
35-fit failed receipt and measurements below remain unchanged; the other four
arms were not rerun. No combined current-source five-arm pass is claimed. Current
launch conditions use reviewed, merged source and the approved operational
funding gate in the [readiness ledger](workshop-readiness.md#paid-launch-assessment).

## What ran

The merged runtime from PR 14 (`3b4a385`) ran the
[current preflight recipe](targeted-preflight.md): Fashion-MNIST, five arms,
one repeat with seed 42, seven fits and 300 seconds per arm, $2 API guards,
four shared CPU cores and serialized MPS. All 49 runtime source files matched
the prior offline confirmation. These are real OpenRouter/Anthropic calls,
not scripted decisions.

The suite is retained locally at
`study-runs/fashion-targeted-preflight-20261021-011538`.
Its [portable receipt](evidence/revised-preflight-2026-10-21.json) records the
configuration, identities, original audit errors and evidence hashes. The full
journals, model artifacts and HTML report remain local; the receipt alone cannot
independently reconstruct them.

| Arm | Best validation accuracy | API cost | Run seconds | Lesson-update events | Later researcher contexts with lessons |
|---|---:|---:|---:|---:|---:|
| Researcher alone | 85.20% | $0.159504 | 87.59 | 0 | 0 |
| Frequent supervision | 84.83% | $0.398727 | 210.70 | 4 | 4 |
| Periodic supervision | 85.40% | $0.315105 | 154.69 | 2 | 6 |
| Periodic + reflection | 87.00% | $0.418557 | 182.84 | 7 | 5 |
| Periodic + reflection, memory off | 86.40% | $0.373128 | 167.49 | 0 | 0 |

The receipt supplies exact context counts and measurements. Four arms reached
85%; none reached 88% or 90%. One adaptive trajectory per arm cannot rank
strategies or establish a memory benefit.

## Execution passed; memory acceptance failed

- **35/35 fits completed and artifacts verified**, with all runs stopping at
  their seven-fit cap.
- **65 model calls, 429,259 input-plus-output tokens and $1.665021** in complete
  accounting. The before/after key-allowance difference reconciles exactly.
- The suite finished reporting about **442 seconds after the first run started**.
  Validation-only postrun work skipped held-out scoring as declared.
- Scheduled reviews and reflections completed. The three supervised memory-on
  arms saved lessons and supplied them to later calls. The control omitted the
  lesson context field and produced no lesson updates.
- The periodic arm proposed an equivalent configuration twice. Both proposals
  reused an earlier observation, with no extra fit or trial slot; their call costs
  remain counted.
- Independent audit: **FAIL, two errors, zero warnings**, launcher exit 2.
  Both errors concern researcher-alone memory: no saved/delivered lesson, and
  the consequent missing final journal register. No separate artifact,
  accounting, scheduling or held-out-isolation error was reported.

## Why offline coverage missed this

The solo arm received an empty lesson register and a tool schema allowing
`lesson_updates`. Every one of its seven responses omitted that optional field.
The instruction says “You may provide at most two”; the controller correctly
persists only supplied nonempty updates. Nothing was dropped.

Acceptance requires each enabled arm to demonstrate writing and later delivery.
The then-implemented request contract permitted omission. The scripted `FakeModel`
automatically supplies a lesson when evidence is available, so earlier checks
proved persistence and isolation without exercising a live model's omission.

The corrective action was to require a cited, scoped observation note through
the existing update field on each eligible researcher decision with completed
citable evidence while its register remains empty. Inconclusive observations
are valid; no invented insight or causal conclusion is required. Existing turn
and resource budgets bound repairs before another fit. Omission, empty updates,
first-call and failed/uncitable-evidence exemptions, equivalent proposals, later
delivery and memory-off isolation now have offline coverage. Researcher notes
persist when a new fit is admitted; reused or deadline-skipped proposals do not
fill the register. Once it is nonempty, further updates are optional.

## Subsequent targeted correction

The corrected source passed **961 tests in 145.14 seconds** and was revalidated
only in the failed `researcher_alone` arm. The
[new receipt](evidence/solo-memory-revalidation-2026-10-21.json) records **seven
fits, seven calls, $0.163809 and 92.816 seconds**, with **85.4667% best validation
accuracy**. Three lesson-update events revised one saved ID; the first note was
saved before fit 2 and delivered to five later researcher contexts. There were
zero invalid decision attempts. The single-run audit passed with **zero errors
and zero warnings**, and all 49 runtime source files matched the corrected
checkout. Held-out scoring remained disabled.

This establishes the repaired solo writing/delivery behavior. The original four
other arms retain their earlier evidence; no full five-arm paid rerun occurred
and this does not establish strategy benefit. Fresh Copilot review, merge into
`main`, and final host and operational budget checks precede overnight launch.

## Human trace review

The trace contains useful mechanisms and imperfect model reasoning:

- Frequent supervision changed CNN epochs from 3 to 5; a scoped observation of
  the resulting validation scores entered later researcher and supervisor
  contexts. This proves delivery, not that memory caused a better choice.
- The control's researcher corrected supervisor advice to exceed the allowed
  channel count and chose a valid batch-size experiment instead.
- The two reflection arms executed identical first four configurations despite
  memory reaching the enabled arm before trial 3. Their later divergence is
  descriptive evidence, not an isolated causal memory effect.
- Model prose sometimes credits the supervisor for a reflection recommendation,
  misstates a score difference, or describes a joint parameter change as
  informative about one parameter. Grounded measurements, configurations and
  source contexts remain available to check those statements.

Treat response labels as self-reported advice uptake. Contract acceptance verifies
structure and references; it does not certify scientific interpretation or the
source attribution in free text. Retained interpretation prose is marked
unverified and excluded from delivered compact lesson context.

## Cost, funding and host checks

The original provisional projection scaled each arm's observed API cost per elapsed second
to 600 seconds and three repeats:

`3 × sum(600 × arm cost / arm elapsed seconds) = $18.48`.

A **30% planning reserve gave $24.03**. These values describe the original run,
before the correction. They are budgeting assumptions, not a confidence interval
or a billing ceiling. Longer histories, provider latency and configuration
choices can change usage. Fifteen $5 guards still sum to $75 and permit in-flight
overrun.

The key allowance was checked before and after the run and covered that
provisional buffered estimate. Numeric account/key receipts remain ignored
locally. **Underlying account balance is unverified:** the credits endpoint
returned 403 for the regular inference key, and the browser was signed out.
Successful pilot billing proved that those calls were funded. No credits were
purchased or limits changed.

AC power, a charged battery, approximately 1.8 TiB free space and available MPS
were confirmed before execution. Current launch conditions are recorded below
and in the [readiness ledger](workshop-readiness.md); the
[milestone checklist](workshop-milestones.md) tracks workshop work.

## Current planning and launch basis

The [updated projection](solo-memory-revalidation.md) replaces only the original
solo cost/time rate with the corrected solo rate: **$18.38**, or **$23.89 with a
30% reserve**. The original four other rates remain cost planning inputs; this
does not combine the runs into new scientific evidence.

The user authorized autonomous launch from reviewed, merged `main` after final
host checks and a fresh key allowance/effective budget covering that buffered
forecast, together with successful billed pilot calls. Keep the $5 per-run
guards, provider key cap and unknown-cost stops. Underlying account balance
remains unavailable through the inference key (403); independent account-wide
balance visibility is not a required gate and is not claimed. No purchase or
limit increase is authorized. The dated run logs record actual launch status.
