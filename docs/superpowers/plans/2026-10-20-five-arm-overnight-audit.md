# Five-arm overnight configuration and audit implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the approved overnight comparison reproducible and automatically distinguish completed search from verified interaction coverage.

**Architecture:** Add a dedicated configuration and an offline audit module. Expose the audit as a standalone CLI command and an opt-in suite postrun gate; leave the experiment controller and scientific protocol unchanged.

**Tech Stack:** Existing Python standard library, study report/config/accounting helpers, pytest.

**Spec:** The user's accepted high-level review and `docs/targeted-preflight.md`. The user explicitly authorized implementation, testing, commit, PR and merge; no paid overnight launch is authorized in this task.

## Global Constraints

- Five `apprentice_interactions` arms; Night Science, literature off, memory only in the final arm.
- Three matched repeats, seeds 42–44; 600 seconds/run, $5 guard/run, trial safety cap 1000.
- Preserve existing model/provider, data, targets and search bounds; four shared cores/MPS; two-hour suite window with 1200-second postrun reserve.
- Audit reads saved data and hashes artifacts without unpickling, scoring, or network access. Only its own JSON summary is written.
- Pass/warning/fail: recovered contract repairs warn; missing/inconsistent runs, artifacts, accounting or interactions fail.
- Historical sources may differ from the current checkout: report that separately rather than invalidating old evidence.

## Review Focus

- Missing/truncated/corrupt artifacts must fail with an actionable result, not silently omit a run.
- Unused or leaked memory must fail despite a normal search stop.
- Recovered formatting errors must warn; unresolved invalid contracts must fail.
- Repeated-run identities and saved report comparisons must agree with the declared schedule.
- Validation-only versus held-out completion must be explicit; audit must never perform evaluation itself.

### Task 1: Configuration, reusable audit and launch recipe

**Files:** Create `study/fashion-five-arm-overnight-config.json`, `study/audit.py`, `tests/test_audit.py`, `docs/five-arm-overnight.md`; modify `study/__main__.py`, `study/README.md`, and the root README entry point.

**Interfaces:** `audit_suite(root: Path) -> dict` returns `passed`, `status`, `errors`, `warnings`, per-run evidence and totals. `write_audit(root: Path) -> dict` saves `audit-summary.json`. `study audit --output ROOT` exits 0 for pass/warning, 2 for failure. `suite --audit` runs the same audit after execution/reporting, including retaining a failed audit when postrun work fails.

- [x] Add regression fixtures using the real controller/suite and scripted model, with only training stubbed; mutate copies to cover all five review-focus cases. Verify failing tests before implementing.
- [x] Implement the config, audit and CLI integration. Check exact expected arm identities, configs, seeds, event/summary accounting, completed artifact hashes, schedules, advice, memory delivery, repairs, four matched contrasts and postrun policy.
- [x] Test CLI exit/status output, stale reports, missing files, incomplete calls, malformed records and artifact tampering. Run the new tests, then the full suite.
- [x] Audit the saved live and offline preflights plus the controller-backed 15-run fixture. Document the two-hour launch with `--repeats 3 --reserve-seconds 1200 --audit`, held-out evaluation after frozen search, retained logs/exit code and no automatic paid retries.
- [x] Obtain one fresh whole-change review and resolve important findings.

**Integration:** Commit/push `feat/five-arm-overnight-audit`, open/attach/merge its PR without waiting for GitHub CI, synchronize main, and assess readiness. The merge outcome is recorded in the parent workspace running memory after integration.

## Execution ledger

- User approved this scope and integration; implementation remains in the existing checkout on a new branch, following the established workspace preference.
- Source/refactoring changes outside the audit/config/CLI/docs boundary are deferred.

- Regression evidence: initial missing audit/config tests failed before implementation; review added 15 failing cases covering selection truth, actual fit seeds, accepted contracts, reflection ordering/delivery, call statuses, final cadence, repaired skipped decisions, and metric bounds/consistency. All 44 focused audit tests now pass.
- Saved live preflight audit: five runs, 35 verified fits, 68 calls, $1.665228, four matched contrasts; zero errors, one historical-source warning and one repaired-contract warning. Saved offline preflight: five runs/35 verified fits, zero errors, historical-source warning only. No paid calls or held-out scoring were performed.
- Launch recipe passed `bash -n`; the paid launch command was not executed.
- Independent review completed after fixes: no remaining merge blockers. The reviewer independently verified the audit tests and final metric regressions.
- Final verification: `python -m pytest -q` — 732 passed in 127.88 seconds; `git diff --check` clean. Both saved preflight audits still pass after the final metric checks.
