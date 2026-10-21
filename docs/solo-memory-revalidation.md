# Solo memory contract: targeted revalidation — 21 October 2026

**PASS for the repaired researcher-alone arm.** Only the failed arm was rerun;
the other four paid arms were not repeated. This is not a new five-arm suite or
a combined current-source comparison. The [original five-arm failure](revised-preflight-results.md)
and its [portable receipt](evidence/revised-preflight-2026-10-21.json) remain unchanged.

## Fix and verification

An enabled, empty lesson register now requires one scoped observation at the
first researcher decision with a completed, citable numeric measurement. The
request schema, instructions and canonical validator agree. Existing bounded
contract repair rejects omission or an empty update before another fit starts.
A factual or inconclusive observation is enough; no scientific insight is forced.
The initial decision, failed or uncitable history, and memory-off control remain
exempt. After a note exists, later updates are optional. Notes persist only with
an admitted experiment; an equivalent or deadline-skipped proposal does not seed
the register. See [the memory contract](memory-default.md).

The omission regressions failed against the previous runtime (10 failures, three
passes). With the fix, 126 focused checks and the full **961-test suite** passed
(the full suite took 145.14 seconds). Coverage includes missing/empty updates,
bounded repair and charged failed calls, persistence and later delivery,
recovery/reset, exempt histories, the control, and equivalent proposals.

## Paid result

| Measurement | Result |
|---|---:|
| Completed fits / verified artifacts | 7 / 7 |
| Real provider calls | 7 |
| Recorded API cost | $0.163809 |
| Tokens, input / output | 39,113 / 3,098 |
| Elapsed search time | 92.816 seconds |
| Best validation accuracy | 85.4667% |
| Lesson update events / final IDs | 3 / 1 |
| Later researcher contexts with lessons | 5 |
| Audit errors / warnings | 0 / 0 |

The ledger started empty. Its first note was saved before fit 2 and delivered to
later decisions. Three events revise one ID; they are not three distinct lessons.
The live model obeyed the required update on its first attempt, so omission and
repair are established by the regression cases, not a live repair event. The run
stopped at the seven-fit cap, with complete accounting and no held-out scoring.

Raw evidence is retained locally at
`study-runs/solo-memory-revalidation-20261021-014632`, including journals,
artifacts, provider records, report, verifier and `single-run-audit.json`.
The [portable receipt](evidence/solo-memory-revalidation-2026-10-21.json) records
all 49 runtime source hashes and five raw-evidence hashes. Independent review
replayed the provenance/run audit and checked contracts, delivery, billing and
artifact hashes. This single-run audit does not claim suite-level matched pairs,
five report groups or completed overnight evaluation.

## Launch assessment

Replacing only the original solo arm's cost/time rate yields a provisional
**$18.38** projection for the fifteen 600-second runs, or **$23.89 with a 30%
planning reserve**. The four other historical rates are cost-planning inputs;
they do not become current-source experimental evidence. Linear extrapolation
and its reserve are neither a confidence interval nor a billing ceiling.

The refreshed inference key allowance/effective budget covers that buffered
forecast and the completed pilot was billed successfully. Account-wide credit
balance remains unavailable to this inference key (HTTP 403); no credits were
purchased or limits changed. Under the user's explicit autonomous launch
instruction, use the verified key allowance, existing $5 per-run guards,
unknown-cost stop policy and provider key cap. Fifteen guards sum to $75, and
in-flight calls can overrun a guard. Refresh budget and host checks at launch;
stop on actual funding/accounting failure and retain evidence.

PR [15](https://github.com/jakeberv/NightAgent/pull/15) records the fix and fresh
review. Merge reviewed changes and verify the launch checkout matches this
runtime before starting the [overnight recipe](five-arm-overnight.md). Current
operational status belongs in [readiness](workshop-readiness.md) and the local
suite logs. This revalidation itself neither launched overnight nor scored the
official test set. A delivered note establishes delivery, not a memory benefit.
