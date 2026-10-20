# Focus and live progress chart implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make measured experiment progress the main visual in the default Focus view, with stable strategy selection and no added API usage.

**Architecture:** Record compact per-trial observations in Findings; render a local terminal scatterplot and best-so-far step line. StatusLine owns presentation keys and selection; ConsoleProgress retains independent run states. Neither rendering nor keyboard input changes experiments.

**Tech Stack:** Python, Rich, pytest, existing POSIX keyboard reader.

**Spec:** User-approved proposal in this chat: Focus first, actual validation objective, dots at completion time, best-so-far line, target lines, time/cost/token axes, latest complete-sentence narrative and lesson, accessible compact fallback, stable run selection, full-run history, no extra model calls.

## Global constraints

- New branch from main; preserve unrelated recovery-fix checkout.
- No paid API calls, scientific objective changes, fake scores or inferred convergence.
- Cost/token axes use cumulative run accounting at completion; incomplete coordinates are omitted and explicitly labelled.
- Keep existing f/l shortcuts, Ctrl+C and alternate-screen flicker protections; add x axis and [/] run selection.
- Entire sentences, literal sanitized agent text, monochrome/ASCII chart support.

## Tasks

### Task 1: Progress observations and chart

Files: study/findings.py, new study/live_chart.py, tests/test_live_chart.py.
Produces: complete history with elapsed/cost/tokens, chart(state, width, height, axis, ascii_only), progress_sentence(state).

- [x] Write failing tests for >80 observations, unknown accounting, minimization, ties, failed trials, exact time placement and step geometry, empty/single result, bounds and ASCII rendering.
- [x] Run tests and observe feature failures.
- [x] Implement observation snapshots and cached, labelled full-run chart with target lines and stable expanding bounds.
- [x] Run targeted tests; expect all passing.

### Task 2: Focus hierarchy and stable navigation

Files: study/focus.py, study/terminal.py, study/keyboard.py, study/progress.py; tests/test_focus.py, tests/test_terminal.py, tests/test_progress.py.
Consumes: chart and progress_sentence from Task 1. Produces default Focus, x axis cycle, [/] explicit run navigation and preserved per-run state.

- [x] Add failing tests for default Focus, concurrent run stability, completion, key navigation/paste handling, dimensions and sentence retention.
- [x] Implement compact hierarchy: activity, best/target/gap, chart, progress sentence, narrative, lesson, budgets/resources. Hide chart before critical text on tiny terminals. Details replaces redundant sparklines with same chart when space permits.
- [x] Run UI tests, updating assertions for deliberately changed defaults; expect all passing.

### Task 3: Documentation, review and delivery

- [x] Document keys, accounting/time semantics, target and error treatment, display-only costs.
- [x] Render representative 80x24, narrow and wide screens and exercise real PTY navigation/Ctrl+C.
- [x] Run complete offline pytest suite and git diff --check: 605 passed on main 63e7a81 plus this change.
- [x] Obtain independent whole-branch review; fix actionable findings with regression tests.
- [ ] Commit, push feat/focus-live-chart, open and attach PR to main, inspect CI. Do not merge without specific approval.

## Review focus

- Interleaved runs or one run stopping must not switch or mix the displayed chart.
- Accounting may be absent/incomplete; never invent zero costs or add cached/reasoning token subsets twice.
- Dense plots can have multiple experiments per terminal cell; preserve best improvements, document resolution.
- Resize, long prose and Unicode must not erase budgets or split sentences.
- Long idle API intervals must not create new experiment points or repeatedly rescale the chart.
