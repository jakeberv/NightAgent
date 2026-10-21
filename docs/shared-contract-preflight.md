# Shared-action contract preflight — 21 October 2026

The simplified contract completed its targeted paid operational check. All 24 fits
and artifacts verified, with complete per-call accounting and zero independent
run-audit errors or warnings. The deliberately strict zero-duplicate target
**failed**: one periodic proposal reused an existing observation and recovered on
the next call. The original strict verification remains unchanged.

This is a three-arm validation-only check of the revised framework. It is not a
full five-arm acceptance or evidence of which interaction strategy works best.
No held-out labels were scored and no new full study was launched.

| Arm | Fits | Calls | Cost | Duplicate proposals | Best validation accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| Periodic, memory on |10|15|$0.485286|1|87.60%|
| Periodic + reflection, memory on |7|16|$0.477777|0|87.10%|
| Periodic + reflection, memory off |7|16|$0.430368|0|88.07%|

Total: **$1.393431**, 47 model calls, 368,061 input/output tokens, 21 MPS neural fits
and 3 classical CPU fits. All attempts used seed 43 and stopped at their intended
fit caps under individual $1 guards. The periodic attempt crossed reviews 3, 6 and 9
and executed fit 10, beyond the previous seed 43 no-progress failure. Single
trajectories and different fit caps do not support a strategy ranking.

## What changed

- Supervisor and reflection suggestions use the same configuration schema and
  bounds/equivalence checks as execution. Invalid or completed suggestions are
  repaired before becoming feedback.
- Researchers submit parameters once. The harness derives the recorded change
  against the baseline's effective settings, including defaults and aliases.
- Advice completion is derived from the existing registry, with no additional
  planning state. Every role sees the immutable training seed.
- `structured_v2` marks the action contract. Saved v1 metadata remains readable;
  new execution requires v2. The documented pilot presets were updated, and the
  terminal UI/demo show readable configurations.

## Failure replay and live traces

Offline replay translates the original recorded prose intentions into the new
configuration contract. It covers the 150-tree recommendation outside the 100-tree
limit, unsupported seed changes, old MLP trial 5 beyond the 12-trial history window,
fulfilled cadence advice, and conflicting model-authored change prose. The test
fixtures do not depend on local paid journals.

Fresh verification passed 1,120 full-suite tests and four additional pilot-config
checks added after that collection. All eight named engineering cases passed,
covering 62 checks. Independent code review found no remaining material blocker.

All 22 live accepted suggestions were valid and novel at acceptance. Fulfilled
review annotations reached later researcher contexts in every arm. Each memory-on
attempt saved notes and delivered them later; the memory-off control emitted no
memory updates and supplied no lesson context. Recovery and rejection paths
exercised in offline replays were not triggered for live advisor contracts.

The remaining duplicate is explicit in periodic journal lines 103–111. The agent
acknowledged that trial 7 had fulfilled the recommendation, then tried to increase
channels while already at the maximum 16. Its submitted configuration was unchanged.
The harness recorded no effective change, skipped the duplicate fit and returned
the previous observation. The next call changed channels 16→12 and progressed.
That rejected proposal cost **$0.03744 and 14.18 seconds**. There was no repeated
proposal loop, failed fit, unknown billing or manual intervention.

Independent review classifies this as a recovered planning error. Another
framework layer or paid rerun solely to obtain a zero count is not recommended.
A larger study may be considered with these occasional errors measured as
outcomes; duplicate-free behavior and freedom from future stalls remain unproven.

## Evidence

The [portable receipt](evidence/shared-contract-preflight-2026-10-21.json) preserves
both the operational result and strict zero-duplicate failure. Full local
records, 51 frozen source hashes, the source archive, original verifier result,
artifact hashes and receipts are under
`study-runs/shared-contract-preflight-20261021/`. The interrupted original study
remains separate and unchanged; it is incomplete diagnostic evidence.
