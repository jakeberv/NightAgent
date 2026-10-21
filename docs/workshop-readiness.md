# Workshop readiness — 21 October 2026

The current [specification](../SPEC.md), [protocol](workshop-protocol.md) and
[launch recipe](five-arm-overnight.md) use the revised memory-default design.
`researcher_alone`, `frequent`, `periodic` and `periodic_reflection` use lesson
memory; `periodic_reflection_no_memory` is the matched memory-off control.
The first three contrasts hold memory on; the fourth reports memory-on minus
memory-off. Each independent repeat starts empty.

## Current verification

The revision is ready for PR review and is deliberately **not merged**. Main
retains the earlier memory policy until review and integration.

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

All decisions in these new runs are scripted fixtures. These checks establish
implementation behavior, not model strategy or memory benefit. No paid inference,
held-out Fashion scoring or overnight launch occurred. Fresh read-only credit
and host checks remain separate from engineering acceptance.

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

A new bounded paid pilot is required before the
[two-hour overnight recipe](five-arm-overnight.md). The approximately **$18.12**
projection previously extrapolated from seven-attempt preflight costs and times
is historical only. Enabling memory in four main arms changes prompt usage;
that projection is no longer a reliable planning estimate. Preserve the
600-second allowances, Fashion data/targets, fit limits and resource policy.
The fifteen $5 guards sum to $75 and permit an in-flight overrun; they are not a
billing ceiling.

Recheck current key allowance, account funding, AC power and available storage
immediately before paid work. The read-only key check was refreshed at 00:41 Toronto on 21 October; numeric
receipts remain ignored locally under study-runs/memory-default-readiness-20261021.
The account balance remains unverified. Key allowance does not establish underlying account
funding; the earlier account-balance request returned 403. Keep credentials and
raw key metadata out of documents and Git.

The overnight suite has **not launched** and Fashion-MNIST held-out data remains
unscored. After launch, require complete accounting, verified artifacts, frozen
held-out selection and independent audit acceptance before comparative claims.
Three matched repeats support a workshop pilot; delivery of lessons does not
establish a memory benefit or learning between runs.
