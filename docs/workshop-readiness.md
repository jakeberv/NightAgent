# Workshop readiness — 21 October 2026

**Corrected solo runtime validation: PASS.** The
[targeted paid revalidation](solo-memory-revalidation.md) closes the observed
researcher-alone memory gap. The [original five-arm failure](revised-preflight-results.md)
remains unchanged. Autonomous launch is authorized once the corrected source has
fresh Copilot review, is merged into `main`, and passes the final host and visible
budget checks below. No combined current-source five-arm pass is claimed.

The current [specification](../SPEC.md), [protocol](workshop-protocol.md) and
[launch recipe](five-arm-overnight.md) use the revised memory-default design.
`researcher_alone`, `frequent`, `periodic` and `periodic_reflection` have lesson
memory enabled; `periodic_reflection_no_memory` is the matched memory-off control.
The first three contrasts hold memory on; the fourth reports memory-on minus
memory-off. Each independent repeat starts empty.

## Current verification

The first-observation contract correction passed **961 regression tests in
145.14 seconds**. It requires a scoped, cited note on each eligible researcher
decision while enabled memory is empty, with existing bounded repairs and no
extra reflection phase. Omission, empty updates, failed/uncitable evidence,
equivalent proposals, later delivery and memory-off isolation are covered. The
[solo receipt](evidence/solo-memory-revalidation-2026-10-21.json) records the
checks and frozen source hashes. Fresh review and merge must be verified before
launching this source from `main`.

PR 14 was merged into `main` on 21 October 2026 at `3b4a385`. Its earlier
memory-default verification is retained at its recorded source:

- Full regression: **947 passed in 154.23 seconds** on the combined change.
- [Eight engineering cases](evaluation-cases.md): **8/8 passed, 52 underlying
  checks**. [Portable acceptance receipt](evidence/memory-default-acceptance.json).
- New 15-run rehearsal: **240 real synthetic-data CPU fits**, 432 scripted calls,
  240 verified artifacts, all trial-cap stops and three pairs per contrast.
  All four enabled arms wrote lessons and delivered them to later researcher
  contexts; the control wrote none. Every repeat started empty. Its retained
  source warning identifies code changes during the validation pass.
- Final five-arm confirmation after all fixes: **35 real CPU fits**, 63 scripted
  calls, **audit PASS with zero errors/warnings** and current source hashes.
- Fashion-MNIST solo check: **three real MPS fits**, verified artifact hashes,
  two lesson updates and a saved lesson delivered before trial 3. No test scoring.
- [Portable verification receipt](evidence/memory-default-verification.json)
  records run locations, arm-level memory coverage, hashes and audit results.
- Compilation, 114 local links, whitespace and launch-script syntax pass. The
  shared current tabs match the revised text, unrelated historical tabs are
  preserved, and the native spec was visually verified on one page.
- Independent review found and fixed an audit gap accepting forbidden updates
  in the memory-off control, including empty update fields. Twelve regressions
  cover all roles and successful repair of invalid attempts. A new
  [Copilot finding on PR13](copilot-review-followup.md#new-pr-13-finding--included-in-the-memory-default-pr)
  about double-counted preprocessing metadata is also fixed with full-config
  contract/lesson regressions. Re-review found no important remaining issues.

All decisions in the offline runs above are scripted fixtures. These checks
establish implementation behavior, not model strategy or memory benefit. They
made no paid calls and did not score held-out Fashion data or launch overnight.
The revised paid preflight and launch assessment are recorded separately below.

## Revised paid preflight and solo correction

The 21 October [real-provider preflight](revised-preflight-results.md) completed
all **35 fits**, verified all artifacts, and made **65 calls / 429,259 tokens**
for **$1.665021**. All runs stopped at the seven-fit cap; reporting completed and
held-out scoring was skipped. The original audit matched all 49 current runtime
source files and returned **FAIL: two memory errors, zero warnings**.

Researcher alone saved no lesson and delivered none later. Its optional
`lesson_updates` field was omitted in every response. The three supervised
memory-on arms wrote/delivered lessons; the control wrote none and omitted the
lesson context field. This exposes a request-contract/acceptance mismatch, not
lost writes. The missing final register is a consequence of the same absence.
The [portable failed receipt](evidence/revised-preflight-2026-10-21.json) preserves
the outcome. Do not mark this suite accepted or generate an accepted demo from it.

The corrected contract was then tested and revalidated only in the failed solo
arm: **seven fits, seven calls, $0.163809 and 92.816 seconds**, with **85.4667% best
validation accuracy**. Three lesson-update events revised one saved ID; the
first note preceded fit 2 and reached **five later researcher contexts**. There
were no invalid decision attempts. The single-run audit passed with **zero
errors and zero warnings**, and all 49 runtime source files matched the corrected
checkout. See the [result and receipt](solo-memory-revalidation.md).

The other four arms were not paid rerun. Their earlier observations remain
evidence from the original source, not a combined new five-arm acceptance result.
The prior 947-test fixtures did not expose the live omission path; the current
961-test result and targeted live run establish the correction's coverage, not
strategy benefit.

## Documentation review

The [documentation guide](README.md) separates the public overview, first local
run, operator reference, scientific protocol, milestone checklist and dated
history. [Project goals](project-goals.md) explain the original apprentice
ambition and the narrower workshop test. The
[milestone checklist](workshop-milestones.md) maps the supplied requirements to
artifacts and identifies remaining workshop acceptance, ownership, submission
and presentation work.

The earlier documentation pass changed no runtime code. Its first-run command completed
all five arms with 20 real CPU fits on synthetic data and zero paid calls; offline
report rebuilding also passed. The updated spec and shared current tabs were
read back against the local text, historical tabs were preserved, and the
421-word Markdown spec was visually verified on one PDF page. Link, heading and
whitespace checks passed. Its 947-test regression result describes that earlier
checkout; the correction's current 961-test result is recorded above.

The [Copilot review on PR 14](https://github.com/jakeberv/NightAgent/pull/14#pullrequestreview-5595106330)
reported no open issues and called for human review of the scientific treatment
mapping and launch protocol. The user completed review and merged the PR.

## Retained historical evidence

- The [fixed reference](fixed-reference.md) measured **81.03% validation accuracy
  in 4.74 seconds**, with a verified artifact and frozen identities, no model
  calls and no held-out scoring. Its scientific settings are unchanged.
- The [portable real replay](evidence/fashion-demo/demo.md) and
  [evidence JSON](evidence/fashion-demo/demo.json) remain available from a fresh
  clone. They record the former memory policy and are historical mechanism
  evidence, not a preflight of the revised mapping.
- The [earlier paid preflight](targeted-preflight.md#historical-live-results--2026-10-20)
  completed 35 fits and 68 calls for $1.665228, with best validation accuracies
  of 85.4%–87.5%. Retain its historical-source and repaired-contract warnings.
- The earlier **863-test regression**, **8/8 acceptance cases with 51 underlying
  checks**, [portable receipt](evidence/workshop-acceptance.json), and prior
  15-run/240-fit rehearsal describe the previous checkout. They must not be
  relabeled as fresh verification of this correction.

## Paid launch assessment

The [updated planning projection](solo-memory-revalidation.md) is **$18.38** for
fifteen 600-second runs, or **$23.89 with a 30% planning reserve**. It substitutes
the new solo cost/time rate into the original four arms' rates solely for cost
planning. Linear scaling and the reserve are not a confidence interval or a
billing ceiling, and do not combine the runs into new scientific evidence. The
earlier $18.48/$24.03 and $18.12 estimates remain historical. Preserve the frozen
data, targets, 600-second allowances and resource policy.

The approved operational funding gate uses a freshly verified key allowance and
effective budget covering the buffered forecast, together with successful billed
pilot calls. Those checks passed for the targeted revalidation and must be
refreshed immediately before launch. Keep the existing **$5 per-run guards** and
provider key cap; fifteen guards sum to $75 and permit an in-flight overrun.
Unknown-cost stops remain enabled. No credits are purchased or limits raised.
Numeric account/key receipts remain ignored locally.

**Underlying account balance remains unavailable:** the account-credit request
returned 403 for the inference key. The authorized launch uses the operational
gate above; independent account-wide balance visibility is not required and is
not claimed.

AC power, a charged battery, approximately 1.8 TiB free space and available MPS
were confirmed before the pilot. Recheck power, free space, MPS, key allowance
and effective budget on the reviewed, merged `main` immediately before launch.
The user authorized proceeding autonomously when those conditions pass, without
further intervention. Keep credentials and raw account metadata out of documents
and Git.

The dated overnight run directory's manifest, console log, launcher exit code,
`completion.json` and audit record actual launch and completion status. After
launch, require complete accounting, verified artifacts, frozen held-out selection
and independent audit acceptance. Three matched repeats support a workshop pilot;
lesson delivery alone does not establish benefit or learning between runs.
