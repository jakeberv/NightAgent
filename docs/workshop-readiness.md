# Workshop readiness — 21 October 2026

**Original overnight acceptance: FAIL.** The
[15-attempt overnight comparison](overnight-results.md) produced **349 verified
fits**, but two timeout stops and an unrepaired final supervisor note caused
**seven audit errors and 18 warnings**. Evaluation/reporting completed after
search froze. **$22.444005 is known cost, a lower bound with two calls' billing
unknown.** The original saved audit and run evidence remain unchanged.

The current [specification](../SPEC.md), [protocol](workshop-protocol.md) and
[launch recipe](five-arm-overnight.md) use the memory-default design.
`researcher_alone`, `frequent`, `periodic` and `periodic_reflection` have lesson
memory enabled; `periodic_reflection_no_memory` is the matched memory-off control.
Each independent repeat starts empty. The overnight run verifies saved-note
creation and later delivery in all 12 enabled runs, with none in the three
controls. It does not establish a winning strategy or a memory benefit.

## Reliability correction

The corrected source passed **1,056 regression tests in 158.62 seconds** and
**8/8 named engineering cases**, with 52 underlying checks. The
[verification receipt](evidence/overnight-reliability-verification.json) freezes
source hashes and evidence locations.
Independent review found and fixed a nonfinite-JSON edge case that could lose a
failed-call journal record; re-review found no remaining blockers. New regression
cases reproduce timeout/receipt failures, explicit terminal abandonment and
configuration reuse beyond recent history. Copilot identified two additional
audit boundaries: known-billing failed repairs before a skipped retry, and
oversized numeric budgets. Both are fixed with failing-then-passing regressions
and independent re-review. Related unrepresentable charges remain unknown
instead of crashing accounting.

- The provider owns its total timeout, retains generation headers before body
  reads, and uses one bounded lookup of a matching finalized receipt for actual
  billing. Known billed failures can retry within existing limits; unresolved
  cost still stops. Timeout receipts do not retroactively repair the old records.
- Only an explicitly rejected terminal review, matching skipped repair and normal
  deadline stop with no later activity, receives an abandonment warning. Invalid
  framing and nonterminal/unmarked invalid contracts still fail audit.
- All arms receive a compact registry of completed configurations and persistent
  reuse feedback. Scientific choices remain with the agent; aliases, inactive
  parameters and repeated proposals remain guarded. The measured 42-fit registry
  adds about 7.6 kB (47%) to context, so live duplicate reduction and token cost
  still require a pilot.

The [PR 16 and CI record](https://github.com/jakeberv/NightAgent/pull/16) supplies
review/integration status. Merge requires fresh Copilot findings resolved and
both required CPU CI jobs passing on the final head. No paid rerun or new
five-arm acceptance is claimed. The original suite still fails with its same
seven errors when replayed, and its saved audit remains unchanged.

## What can be demonstrated now

The [presentation walkthrough](../DEMO.md) provides two honest recorded options:

- The [portable historical replay](evidence/fashion-demo/demo.md), available from
  a fresh clone, shows the previous memory policy and retains its source and
  repaired-contract warnings.
- A [manual overnight trace](overnight-results.md#a-valid-local-mechanism-trace)
  shows a real supervisor recommendation, the executed trial, its lower measured
  accuracy, an inconclusive lesson, and later context delivery under the current
  memory-default mapping. Its
  [portable receipt](evidence/fashion-overnight-2026-10-21.json) preserves the
  measurements and journal locations; full replay needs ignored local artifacts.

Both support a scoped mechanism demonstration. Lesson delivery or a later
citation does not establish a causal effect on the next choice or performance.
The strict demo exporter must reject the failed overnight suite. Do not relax the
acceptance gate or replace the original audit to make an accepted export.

## What requires new validation

First verify the reliability correction offline and finish review/CI integration.
Before a new long run, use a brief paid operational preflight with a freshly
checked key allowance and effective budget. No paid rerun was requested or launched in this correction pass. A refreshed
allowance check covers a small operational preflight, but cannot fund another
full matrix at the observed $22.44 lower-bound cost.

The seed-42 frequent and memory-off attempts lack full historical coverage. A
partial rerun could only fill those historical gaps if the treatment and runtime
policy were unchanged, and would not erase the final-contract audit error. The
context and retry correction changes runtime policy: mixing those new attempts
with old attempts cannot yield an accepted comparison for the corrected system.
A clean current comparative claim needs **all five arms and three repeats from
one frozen source**, complete accounting, held-out scoring after frozen search,
and independent audit acceptance. This full paid rerun is a separate spending
decision; it is not necessary to present the labeled recorded mechanism demo.

## Earlier validation and retained evidence

The [earlier revised five-arm paid preflight](revised-preflight-results.md) is
preserved as **FAIL: two memory errors, zero warnings**. It completed 35 fits and
65 calls for $1.665021, verified artifacts and all 49 source files, and skipped
held-out evaluation. Researcher alone omitted its optional lesson updates and
saved/delivered no lessons; the three supervised enabled arms did, and the
control wrote none. Do not relabel this as accepted evidence.

The [first-observation contract correction](solo-memory-revalidation.md) passed
**961 regression tests in 145.14 seconds** and a targeted paid solo revalidation:
**seven fits, seven calls, $0.163809, 92.816 seconds**, with **85.4667% best
validation accuracy**. Three update events revised one saved lesson; it reached
five later researcher contexts. That run's audit passed with zero errors or
warnings and all 49 corrected source files matched. The other four arms were
not rerun at that validation stage. PR [15](https://github.com/jakeberv/NightAgent/pull/15)
was merged at launch commit `621f225`; the subsequent overnight result above is
a separate, failed suite from that source.

Earlier memory-default verification is retained at its recorded source:

- PR [14](https://github.com/jakeberv/NightAgent/pull/14), merged at `3b4a385`:
  **947 tests**, [8/8 engineering cases](evaluation-cases.md) with 52 checks,
  and a 15-run rehearsal with 240 real synthetic-data CPU fits and scripted
  decisions. [Acceptance receipt](evidence/memory-default-acceptance.json).
- A final five-arm offline confirmation produced **35 CPU fits and 63 scripted
  calls**, with audit PASS and zero errors/warnings. A separate Fashion solo
  check produced three real MPS fits and later lesson delivery.
  [Verification receipt](evidence/memory-default-verification.json).
- The [fixed reference](fixed-reference.md) measured **81.03% validation accuracy
  in 4.74 seconds**, with a verified artifact, no model calls and no held-out
  scoring. Its scientific settings are unchanged.
- The [historical real preflight](targeted-preflight.md#historical-live-results--2026-10-20)
  completed 35 fits and 68 calls for $1.665228. Its
  [portable replay and evidence](evidence/fashion-demo/demo.json) retain the old
  memory mapping and warnings.

Offline scripted decisions establish implementation behavior; they do not
supply language-model strategy evidence. Historical test counts do not describe
the new reliability correction. The [documentation guide](README.md) and
[milestone checklist](workshop-milestones.md) retain the wider project context.

## Original launch funding and host checks

The prelaunch planning projection was **$18.38**, or **$23.89 with a 30% reserve**,
using the corrected solo rate and the earlier four arms' rates. It was a planning
estimate, not a billing ceiling or confidence interval. The overnight known-cost
lower bound is now the relevant observed spending evidence; missing timeout
billing prevents a final total.

At launch, the operational funding gate used a freshly verified key allowance,
effective budget covering the buffered forecast, and successful billed pilot
calls. Underlying account balance was unavailable to the inference key. The
existing **$5 per-run guards**, provider key cap and unknown-cost stops were
retained. No credits were purchased or limits raised. The original authorization
to launch has been fulfilled; it is not authorization for another paid rerun.

The host had AC power, a charged battery, approximately 1.8 TiB free space and
available MPS before the pilot. Any new paid validation needs fresh power, free
space, MPS and budget checks on its reviewed source. Keep credentials and raw
account/key metadata out of documents and Git. Numeric account receipts remain
ignored locally.
