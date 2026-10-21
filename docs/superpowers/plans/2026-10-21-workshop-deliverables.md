# Workshop deliverables implementation plan

> Dated engineering record. For current scope, instructions and review status,
> use the [documentation guide](../../../docs/README.md). Later decisions may supersede this plan.

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. User approved implementation and parallel agents; integrate once and obtain an independent final review.

**Goal:** Make the current experiment, engineering evaluation, measured reference and recorded demo reviewable before authorizing the overnight run.

**Architecture:** Keep the frozen five-arm protocol intact. Add thin offline evaluation and demo entrypoints over existing evidence; update the local and shared protocol; independently check available provider credits.

**Tech stack:** Python 3.12, pytest/JUnit, JSONL study records, Google Docs/Sheets, OpenRouter read-only account endpoints.

**Spec:** `SPEC.md`, `docs/five-arm-overnight.md`; approved workshop review and user instructions.

## Global constraints

- No paid inference or overnight launch in this pass. Reference uses frozen validation data only.
- Five arms, three repeats, seeds 42–44, 600 seconds/run; literature off, memory run-local.
- Use the existing checkout; do not await GitHub CI before merge.
- Never print or commit credentials. Do not invent team ownership or efficacy claims.

## Review focus

- Missing/skipped/failed parametrized tests must fail the named evaluation case.
- Recorded demo evidence must distinguish real model calls from scripted offline fixtures.
- Reference inputs and artifacts must verify against the frozen task and data.
- Historical Copilot suggestions require reproduction against current source before fixes.
- Shared document edits must preserve other tabs and use a revision guard.

## Tasks and ownership

- [x] Evaluation agent: `study/workshop_eval.py`, `study/evaluation_cases.json`, `tests/test_workshop_eval.py`, `docs/evaluation-cases.md`. Write failing runner tests, implement one pytest/JUnit execution and case verdicts, run focused tests and the packaged cases. CLI: `python -m study.workshop_eval --output ROOT`.
- [x] Demo agent: `study/demo.py`, `tests/test_demo.py`, `DEMO.md`. Test malformed/missing evidence, create read-only portable replay from the real five-arm preflight. CLI: `python -m study.demo --suite ROOT --output ROOT [--reference PATH]`.
- [x] Copilot agent: review recent merged PR comments, reproduce important unresolved issues, implement scoped fixes plus regression tests. Report comment links and dispositions; avoid other agents' files.
- [x] Integrator: update ~400-word `SPEC.md`, `docs/workshop-protocol.md`, README links and shared current-protocol tabs. Run the predeclared fixed CPU reference and save a reproducible receipt. Check key/account credits through authenticated GET requests, saving only selected numeric fields locally.
- [x] Integrator: run packaged evaluation, demo replay, full pytest, compilation and whitespace checks; obtain fresh independent review, resolve important findings and repeat affected checks.
- [ ] Integrator: commit, push branch, create/attach PR, merge without waiting for CI, update clean local main, update verified milestone row and workspace memory, then reassess launch readiness without launching.

## Evidence ledger

- Baseline: 791 tests passed in 134.01 seconds on `feat/workshop-deliverables` before edits.
- Remaining results are recorded in the completion update after execution.

- Final verification: **863 passed in 151.78 seconds**; named acceptance **8/8 cases, 51 underlying checks**. Compilation, deliverable links, whitespace and launch bash syntax pass.
- Real reference: accuracy0.8103333333, macro-F1 0.8090350882, ROC-AUC0.9733596296, 4.743576s, verified artifact; zero paid calls and no held-out scoring.
- Real portable replay verified against 11 source hashes and seven journal citations. Fresh review found/fixed adaptive-reference mislabeling with six regressions; no important remaining findings.
- Re-audited prior 15-run/240-fit rehearsal: pass, one expected historical-source warning. Shared current protocol/spec readback exact; native specification visually verified on one page.
- Authenticated credit check succeeded for the key; account balance endpoint requires management access. Numeric receipts remain ignored locally, with no credentials in deliverables.
