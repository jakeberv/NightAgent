# Revised paid preflight — 21 October 2026

**Overnight decision: NO-GO.** The revised five-arm preflight completed all 35
fits, but failed the required researcher-alone memory coverage. Underlying account
funding also remains unverified. The audit criteria have not been weakened, and
no automatic paid rerun or overnight launch was attempted.

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
The implemented request contract permits omission. The scripted `FakeModel`
automatically supplies a lesson when evidence is available, so earlier checks
proved persistence and isolation without exercising a live model's omission.

Before another live comparison, align the request contract with the declared
memory behavior. At the first eligible researcher decision with completed
evidence and an empty register, require a cited, scoped observation note through
the existing update field. Permit an inconclusive observation; require no
invented insight or causal conclusion. Cover omission and bounded repair,
first-call exemption, later delivery and memory-off isolation with offline tests.
Review that prospective change and run a fresh bounded paid preflight. Preserve
this failed result as evidence.

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

A provisional projection scales each arm's observed API cost per elapsed second
to 600 seconds and three repeats:

`3 × sum(600 × arm cost / arm elapsed seconds) = $18.48`.

A **30% planning reserve gives $24.03**. This is a budgeting assumption, not a
confidence interval or a billing ceiling. Longer histories, provider latency,
configuration choices and a memory-contract fix can change usage; remeasure
after that fix. Fifteen $5 guards still sum to $75 and permit in-flight overrun.

The key allowance was checked before and after the run and covers this
provisional buffered estimate. Numeric account/key receipts remain ignored
locally. **Underlying account balance is unverified:** the credits endpoint
returned 403 for the regular inference key, and the browser was signed out.
Successful pilot billing proves that these calls were funded; it does not
establish funding for the overnight matrix. No credits were purchased or limits
changed.

AC power, a charged battery, approximately 1.8 TiB free space and available MPS
were confirmed before execution. Recheck the host and both funding gates at the
actual launch. The [readiness ledger](workshop-readiness.md) and
[milestone checklist](workshop-milestones.md) record the remaining work.
