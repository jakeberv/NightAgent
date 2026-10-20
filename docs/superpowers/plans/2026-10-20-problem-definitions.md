# Problem Definitions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. User explicitly requested implementation and previously authorized parallel agents.

**Goal:** Generalize the runner via declarative profiles and trusted task adapters.
**Architecture:** Separate problem schema/data/science from agent control, and use generic metric results throughout. Keep legacy entrypoints/readers for old artifacts.
**Tech Stack:** Python 3.12, PyYAML safe parser, existing sklearn/numpy/httpx/pytest stack.
**Spec:** docs/superpowers/specs/2026-10-20-problem-definitions.md

## Global Constraints
- Existing checkout and branch; no worktrees or paid model calls. Checkpoint commit completed first.
- User approved implementation; do not repeat design/plan permission requests.
- Keep all five schedules/deadlines/isolated worker/hidden test/unknown accounting protections.
- Scientific definitions are immutable for each prepared dataset/run; no executable user YAML.
- Root owns commits and integration. Parallel agents own disjoint files.

## Shared interfaces
`study.problem.ProblemSpec` constructed with `ProblemSpec.from_dict(value, base_dir=Path('.'))`, `load_problem(path)` returns it. Properties: `id`, `task`, `brief`, `objective` dict {metric,direction}, `targets` list of {name,value}, `dataset` dict, `search_space` dict, `fingerprint` str; `to_dict()` canonical deep dict. `legacy_problem(milestone=.93,stretch=.95)` returns legacy-compatible spec. `problem_from_data(data_dir)` returns ProblemSpec or None if legacy manifest. `assert_problem_matches(data_dir, problem)` validates frozen identity and partition hashes before paid work.
`study.tasks.get_adapter(problem)` returns trusted adapter with `id`, `version`, `analysis_schema`, `reference_config`, `describe(data_dir)` (safe metadata), and async `run_trial(data_dir,trial_dir,config,*,seed,timeout)`. `science.prepare_dataset(..., problem=None)` accepts new profile while existing csv/synthetic args remain for legacy. `science.run_trial` and `evaluate_selected` inspect frozen manifest and dispatch accordingly; generic outputs defined by spec. New tasks may live study/tasks.py (single small registry, no dynamic import from YAML).
Controller `run_one(..., problem=None)` resolves profile from prepared data or legacy config fallback. `tools_for(role,config,problem=None)`, `select_result(...,problem=None)` backwards compatible. Custom trial_runner test injection retains same call signature. Summary: objective dict, problem full dict, problem_hash, target_definitions list, target_selections mapping. Selection: score, metrics, trial_id, elapsed_seconds, artifact/hash, accounting; validation_auc compatibility for roc_auc. Legacy milestone/stretch aliases populated for those named targets only.
Report `build_report_data` keeps old fields for historical ROC-AUC inputs, new `best_score`, `objective`, `targets` mapping name->{threshold,reached,seconds,test_score,...}, generic `best_test_score`. CSV can use long target JSON column plus dynamic columns. No mixing of distinct problem hashes/metric/direction into a misleading aggregate.

## Review Focus
- Minimize RMSE with values outside [0,1], arbitrary target names, correct first crossing/ties.
- Multiclass MNIST original test arrays never used in preprocessing/validation.
- Profile edits, wrong data/schema, invalid metrics fail before model factory.
- Legacy MAGIC invocation and existing reports/schedules remain valid.
- Search-space overrides can't expand trusted bounds or invoke arbitrary estimators.

## Task 1 — profiles and adapters (agent)
Files: study/problem.py, study/tasks.py, study/science.py, study/worker.py; tests/test_problem.py, tests/test_tasks.py, tests/test_science.py; examples under study/problems/.
- [x] Write failing profile/split/schema/metric/preprocessing/dedup tests.
- [x] Implement shared interfaces, CSV/NPZ/synthetic preparation and task registry, metrics, worker/evaluator dispatch.
- [x] Verify task tests and legacy science tests. Report actual commands/results.

## Task 2 — generic control and freezing (agent)
Files: study/controller.py, study/prompts.py, study/config.py, study/suite.py; tests/test_controller.py, tests/test_suite.py.
- [x] Failing tests for min direction, named targets, prompt/schema identity, changed-profile refusal before model factory, recovery.
- [x] Use ProblemSpec and adapter; preserve protocol behavior and legacy signatures.
- [x] Verify controller/suite tests. Report commands/results.

## Task 3 — generic reports (agent)
Files: study/report.py, tests/test_report.py.
- [x] Failing tests RMSE lower best/targets, multiclass accuracy, mixed problems warning/partition, old reports.
- [x] Implement generic read/aggregation/plots/CSV with all planned run accounting intact.
- [x] Verify report tests and inspect plot output. Report commands/results.

## Task 4 — CLI and integration (root)
Files: study/__main__.py, study/fake.py, study/README.md, README.md, requirements-study.*, tests/test_cli.py.
- [x] Tests profile init/validate/prepare/run smoke workflows and invalid configs before provider construction.
- [x] Add profile CLI, fake model adapter-aware choices, generic selection evaluation, setup/examples docs.
- [x] Install PyYAML, freeze verified lock, run all tests and three offline workflows.

## Task 5 — review and finish
- [x] Independent component/whole-change review and fix defects.
- [x] Full tests, compile, whitespace checks; record outcomes and update working memory.
- [x] Commit generalized framework separately after verification. No push.

## Verification outcome

Checkpoint `39f8fd6` preceded implementation. Final full suite: 165 passed in 20.37s; compilation and whitespace checks passed. Three offline five-condition workflows completed; actual MAGIC and official MNIST preparation succeeded. Independent scoped review cleared both findings and CLI/docs integration (96 focused tests). See `docs/study-verification.md`. Generalized changes are committed separately on the existing branch; no push or paid inference.
