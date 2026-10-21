# Study cleanup implementation plan

> Dated engineering record. For current scope, instructions and review status,
> use the [documentation guide](../../../docs/README.md). Later decisions may supersede this plan.

> **For agentic workers:** Execute independent file ownership groups using the dispatching-parallel-agents skill, then perform one fresh whole-branch review. Steps use checkbox syntax for tracking.

**Goal:** Complete the six cleanup recommendations accepted by the user, verify the current framework, and merge before reassessing the overnight launch.

**Architecture:** Keep the current scientific comparison well defined and the study CLI coherent. Extract controller helpers and report responsibilities, centralize version-aware event parsing with explicit recovery/report policies, clarify the two application entry points and configuration presets, and separate locked CI verification from dependency-update checks. Measure history lookup costs before choosing an optimization.

**Tech Stack:** Existing Python 3.12, standard library, pytest, GitHub Actions; no new production dependency.

**Spec:** The six recommendations in the preceding conversation, approved by “Do all of it. Test it, commit and merge without waiting for CI, then reassess before we launch the overnight run.”

## Global constraints

- Work in the existing checkout on `refactor/study-cleanup`, following the established workspace preference. Base: `3fb9dae79707b272ad0159f55f7f6c6f3ddbcc5a`.
- Preserve the five-arm configuration, model/provider, targets, budgets, data and split, model-visible context, treatment schedules, deadline admission, memory semantics and selection rules.
- User steering: historical behavior, saved-run compatibility and old imports need not be preserved. Simplify around the current framework; obsolete compatibility branches may be removed. Keep historical artifacts as reference and label old entry points/presets clearly.
- Introduce explicit event format versioning. Unversioned records may be read only when already structurally compatible; no compatibility emulation is required. Strict auditing fails on malformed/truncated evidence, recovery permits only a partial final append, and reports surface corruption warnings.
- Audit shares low-level parsing only; its scientific cross-checks remain independent of controller execution.
- Never launch paid calls, the overnight run, or Fashion-MNIST held-out evaluation in this task. Fresh offline synthetic fits and synthetic held-out test fixtures are allowed.
- Keep implementer file ownership disjoint and commits/integration with the parent. One final fresh review and consolidated full-suite run before commit/PR/merge; do not wait for GitHub CI.

## Review focus

- Current journal evidence must yield correct selections/accounting and report data; malformed or unsupported formats must be explicit errors/warnings. Do not spend work preserving obsolete formats.
- Deadline/cancellation/retry paths must preserve accounting, resource release, stop reasons, and interaction ordering.
- Helper extraction must preserve researcher/supervisor/reflection contexts, memory isolation, and evidence outside the recent-history window.
- Reports must retain missing/unknown outcomes and correct matched groups, including interrupted runs and incompatible comparisons that must not be pooled.
- Locked CI must actually constrain dependencies (including CPU PyTorch); the range job must stay visibly separate and retain its diagnostic artifacts on failure.

### Task 1: Documentation, preset index, reproducible CI

**Files:** README.md, study/README.md, nightagent/README.md if useful, docs/configurations.md, docs/ci.md, .github/workflows/ci.yml, a CPU lock/constraints file if needed.

**Interfaces:** The current demo command and configuration stay valid. The docs identify the controlled study and conversational prototype separately. The preset index enumerates all `study/*config.json`, their purpose/status, comparison, and budgets. CI has distinct locked-baseline and supported-ranges checks.

- [x] Read existing presets/locks and remove misleading current-scope statements; link the current overnight recipe clearly.
- [x] Index all presets without renaming/deleting historical inputs.
- [x] Separate locked CPU baseline installation from range-update checks; preserve full offline tests and unique diagnostics/artifacts.
- [x] Validate Markdown links, preset inventory, workflow YAML, and installation/constraint logic; report platform verification limits.

### Task 2: Controller helpers and measured history lookup

**Files:** study/controller.py; focused new controller/context/history modules; tests for preserved controller behavior and history handling; a reproducible local benchmark if useful.

**Interfaces:** The CLI, suite, audit and tests use the new focused modules directly where appropriate; obsolete helper re-exports are unnecessary. Extract self-contained responsibilities (context construction, model-call execution, trial execution, selection/recovery as appropriate) using explicit dependencies instead of module-global coupling.

- [x] Characterize current context/event/deadline behavior with existing tests before editing.
- [x] Extract focused responsibilities without changing scheduling, journal order, payloads, or admission arithmetic; use existing passing behavior tests for pure moves and RED→GREEN tests for new interfaces/bugs.
- [x] Measure repeated history lookup work at 7, 16, 100 and 1000 attempts. If meaningful, maintain a run-local index used by evidence/lookup helpers while retaining sequence compatibility and identical model context. Otherwise record the measured reason to defer extra caching.
- [x] Run controller/reasoning/context/admission/reliability tests and report measurement results and compatibility evidence.

### Task 3: Report loading, aggregation, rendering boundaries

**Files:** study/report.py, focused new report-loading/data/rendering helpers, report tests.

**Interfaces:** `build_report_data(root)` and `generate_report(root)` remain the current entry points. Remove obsolete normalization/fallback logic and update obsolete tests where justified; do not preserve private import aliases. Parent will provide `study.records.load_events(path, *, policy='strict', warnings=None)`; report loading may use policy `report` while preserving warning visibility. Do not edit events.py, audit.py, or controller.py.

- [x] Record report behavior using existing saved-run and report tests.
- [x] Extract file/record loading and normalization, aggregation, and HTML/plot generation into focused modules; keep compatibility exports.
- [x] Preserve grouping, first-target crossings, unknown-accounting handling, atomic output, and rendering artifacts.
- [x] Run report/analysis/efficiency/targeted-comparison tests; compare report data on the saved live preflight before/after the refactor.

### Task 4: Versioned event formats and integration

**Files:** study/records.py, study/events.py, study/audit.py, tests/test_records.py, tests/test_events.py, event format documentation; integrate report loader once Task 3 returns.

**Interfaces:** `EVENT_SCHEMA_VERSION = 1`; `validate_event_record(record) -> dict`; `load_events(path, *, policy='strict', warnings=None) -> list[dict]`. Missing version means an unversioned current-shape record; unknown versions fail. No legacy layout translation is required. New journal records carry version 1. The event version governs the embedded trial-result format; keep result/context contents unchanged. `events.read_events` remains recovery-compatible.

- [x] Add failing behavioral tests for format/version/payload validation, corruption policies, and current event consumers before implementing the parser.
- [x] Define typed event/result contracts and implement explicit strict/recover/report reading policies.
- [x] Connect journal writes, recovery reads, report reads and audit reads without sharing scientific acceptance logic.
- [x] Run new record tests plus audit/recovery/report compatibility tests; re-audit saved real-artifact live/offline preflights.

### Task 5: Final verification, review, integration and reassessment

- [x] Inspect all ownership diffs and cross-module imports; resolve conflicts and any new failures with regression evidence.
- [x] Run the full offline test suite and an offline five-arm rehearsal that crosses the 12-trial history window, generates reports, and passes the reusable audit. Do not reuse held-out Fashion data.
- [x] Obtain a fresh whole-branch review; fix important findings, run appropriate checks, and record any remaining limits.
- [ ] Commit/push, open and attach the PR, merge without waiting for GitHub CI, synchronize main, verify its tree matches tested changes, and remove this task's merged branches.
- [ ] Update parent workspace memory and report launch readiness and any outstanding issues.

## Execution ledger

- User authorized all six cleanup areas plus testing, commit and merge; no new permission gate is needed for the already approved scope.
- Pure function moves use the existing regression suite as characterization; new format/index behavior requires failing tests before implementation.
- Parent owns shared event formats, integration, commits, and final review. Independent implementers own docs/CI, controller/history, and reporting respectively.
- User steering before implementation: legacy run behavior and saved-run compatibility are explicitly expendable; overall agent-framework clarity/reliability and project goals take priority. Pure refactors may change internal interfaces, and obsolete tests may be replaced by tests of the current contracts.
- Baseline verified before production edits: 732 tests passed in 128.92s.
- Task 4 RED→GREEN: 23 new format/corruption tests failed before `study.records` existed; parser/writer/audit integration then passed. Two additional malformed-status regressions reproduced TypeError and now reject with ValueError. Focused records/events/audit/progress verification: 84 passed.
- Task 1: docs/CI owner verified all nine presets, 81 local links, 18 documentation Bash blocks, workflow YAML, nine shell scripts and two embedded Python blocks. Linux CPU resolution matches all 47 pins including the official CPU torch wheel; a negative constraint check rejects incompatible torch, and failed installation propagates through tee. Native Ubuntu execution remains CI verification, not a local claim.
- Task 2: focused controller tests passed; five arms ×16 trials compared with the original controller produced identical normalized contexts/events and summaries. Controller reduced 611→297 lines; run_one 397→252. History benchmark maximum optimistic cache saving: 3.148/6.505/34.333/327.553 microseconds at 7/16/100/1000 attempts. Measured decision: keep sequence representation and full evidence visibility, avoid cache-state complexity for sub-millisecond savings.
- Task 3: 92 focused report/comparison tests passed. Current saved live report data remained identical across 35 real fits; report now requires frozen objective/current journal evidence and stages output before publication.
- Integration: first consolidated suite had 774 passes and one stale private report-helper import; import and current result fixture corrected, resources/execution39 passed.
- Recovery simplification: four regressions first proved unsupported frozen policies were being silently coerced and absent frozen science guessed. Removed those compatibility paths; current recovery requires resolved-config.json and honors its declared policies.
- Final review found three important boundaries: a current smoke producer still emitted only test_auc, recovery hid syntactically corrupt final lines, and audit selection replay reused the production selector. Regressions reproduced all three; fixed canonical score/metrics output, conservative unfinished-JSON detection, and independent batch reconstruction of best/first-target selections. Obsolete recovery-policy preservation tests now assert explicit rejection.
- Final-review fixes verified: 87 focused tests pass, including fault-injected production-selector disagreement, corrupt versus partial JSON tails, and canonical synthetic held-out score/metrics. The earlier second full run had 778 passes and one obsolete policy-preservation expectation; it now asserts current-policy rejection.
- Fresh MPS execution check: study-runs/cleanup-mps-check-20261020-234209, two successful Fashion-MNIST MLP fits, both actual device mps, verified hashes, complete accounting, two memory updates, zero paid cost, no held-out scoring. Host on AC with about1.8TiB free.
- Final full offline suite: 791 passed in128.57s, including all review regressions; git diff --check clean.
- Fresh current-framework rehearsal: study-runs/cleanup-rehearsal-20261020-234121/suite, 15 runs ×16 real CPU fits =240 verified artifacts,432 scripted model calls,$0 API cost, every stop trial_cap, four contrasts ×three matched pairs, source hashes match current code, report complete, audit PASS with zero errors/warnings. Synthetic validation-only data; no Fashion held-out scoring.
- Launch assessment before integration: all important review findings resolved by RED→GREEN regressions; current comparison settings remain fixed. Native Ubuntu execution will be covered by the new CI jobs; user explicitly requests merging without waiting for them.
- Public README smoke command executed end-to-end: study-runs/cleanup-public-smoke-20261020-234633, five arms/20 real synthetic fits, completed held-out fixture scores present in every report row, zero warnings. Fashion held-out partition untouched.
- Parent reproduced the history benchmark; optimistic saving at1000 attempts remained about0.33ms. Keeping the simple representation is the measured optimization decision.
- Git integration and final readiness outcome are recorded in the parent workspace README after merge.
