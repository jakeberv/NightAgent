# Study implementation verification — 20 October 2026

Implemented in the existing `experiment/overnight-openrouter` checkout, based on
`dev-ben2` commit `e285fad38fc004ddd76c4a077d961f0403665fa3`. No worktree, merge,
push, paid inference, or overnight comparison was performed.

- Full suite: `python -m pytest -q` — **98 passed in 9.24 seconds**, no warnings.
- `python -m compileall -q study`, CLI help, and `git diff --check` passed.
- Offline end-to-end smoke completed all five conditions with four real
  classifier trials each, scripted model responses, and fixture literature.
  All stopped at the deliberately small smoke trial cap. Best synthetic
  validation AUC was 0.949 in each condition, as expected for identical scripted
  decisions. The identical selected artifact was test-scored once across the
  entire smoke suite. HTML and CSV reports were generated.
- A validation-only MAGIC pilot confirmed bounded classifier execution under
  the exact fixed partition. Best validation AUC was 0.941238; complete trial
  wall times were 1.21–6.10 seconds. No MAGIC test labels were evaluated.
  Configurations, hashes and environment are recorded locally in the ignored
  `study-runs/magic-pilot` directory.
- Public OpenRouter model endpoint/pricing metadata was retrieved successfully
  without inference or credentials. Real authenticated model/tool-call latency,
  provider availability, billing, and literature quality still require a live
  pilot before an overnight study.

An independent component and whole-change review checked experimental controls,
data isolation, cancellation, accounting, and reporting. Findings were fixed and
covered by regressions: fail-closed exclusion of native-search models; unknown
cache/reasoning breakdowns; cancellation during worker spawn; cancelled-request
billing; inclusion of all scheduled runs after interruption; and visibility of
already-saved test scores after postrun evaluation timeout. Final scoped review
found no unresolved actionable findings.

## Configurable problem framework

The initial runner was checkpointed first as `39f8fd6` after 98 tests passed.
The subsequent refactor adds strict YAML/JSON profiles, trusted classification
and regression adapters, generic metric direction and named targets, CLI
validation, and frozen problem/data identities throughout recovery and reporting.

- Final full suite: `.venv/bin/python -m pytest -q` — **165 passed in 20.37 seconds**.
  Compilation and `git diff --check` also passed.
- Offline end-to-end checks each completed five conditions × four real trials:
  synthetic regression (RMSE), three-class CSV classification (accuracy), and the
  original binary synthetic smoke (ROC-AUC). These generated held-out evaluations,
  HTML reports, and CSV summaries, using only scripted model/literature responses.
  The final multiclass and legacy smokes also verified frozen dataset identity.
- The official MNIST archive matched SHA-256
  `731c5ac602752760c8e48fbffcf8c3b850d9dc2a2aedcf2cc48468fc17b673d1`.
  Preparation produced 48,000 training, 12,000 validation and the original 10,000
  test images. No full MNIST fitting or test scoring was performed; the 0.95
  accuracy target remains unproven. Fixture tests cover multiclass NPZ fitting
  and preservation of the official-test arrays.
- The MAGIC profile also prepared the actual source successfully into a separate
  frozen dataset. Its test labels remain unevaluated.
- Independent review findings were fixed with regression tests: incompatible
  class-label representations fail validation, narrowed parameter bounds cannot
  contradict enums, and reports refuse different dataset fingerprints or mixed
  known/unknown identities. The final scoped review found no remaining actionable
  issue, with 96 relevant tests passing independently.
- The verified lock adds PyYAML 6.0.3. The [profile guide](problem-definitions.md)
  documents supported inputs, metrics, targets, commands and extension boundaries.

## MNIST AUC alignment

At the user's request, MNIST now uses `roc_auc_ovr_macro` as its primary metric,
with accuracy and macro-F1 secondary. MAGIC's binary `roc_auc` is unchanged.
Both profiles use provisional 0.93/0.95 targets; matching thresholds does not
establish matched task difficulty.

- Added probability-based macro one-vs-rest scoring and preflight rejection of
  binary sources, ambiguous positive-class settings, and missing classes.
- Final full suite: **176 passed in 24.31 seconds**. Compilation and whitespace
  checks passed. Independent scoped review found no actionable issue; 77 focused
  tests passed, and an independent ten-class check matched scikit-learn.
- Prepared the official MNIST source into `study-data/mnist-auc-profile`.
  All three partition hashes match the earlier accuracy-based preparation exactly:
  48,000 training / 12,000 validation / 10,000 official test images. No full MNIST
  fitting, test scoring, or paid API calls were performed.
- Reports label the metric explicitly as macro one-vs-rest ROC-AUC. New tests
  cover unequal class frequencies, permuted probability columns, worker/held-out
  scoring, and the CLI/controller/report path.

The final study dataset/protocol, model/provider, repeats, run allowance, and
secondary caps remain explicit pilot choices. The implementation and synthetic
smoke do not establish that any interaction strategy is superior.

## Review fixes and short MAGIC pilot preparation

- Full suite: **221 passed in 36.64 seconds**; compilation and whitespace checks
  passed. Regressions cover bounded DOI redirects, validation at each hop,
  timeout ownership, failure provenance, fatal CLI exit status, readable live
  progress, cumulative accounting, and explicit env-file credential loading.
- Independent review found no remaining material issue after the controller's
  competing literature timeout was removed. The literature client owns one
  deadline across DNS, redirects and reading.
- A validation-only MAGIC preflight completed 12/12 classifier trials, three
  supervisor reviews and 11 reflections using scripted model responses. A second
  four-trial preview verified live CLI output, readable logs and reporting.
  Neither run scored MAGIC test data or made model API calls.
- Public OpenRouter metadata listed the pinned Anthropic endpoint. Live Crossref
  search returned five results; the first two fetch attempts encountered a
  publisher HTTP 403 and the bounded redirect limit. Redirect following does not
  remove publisher access restrictions; these failures are recorded as evidence.
- The existing Tutorial 3 env file was successfully parsed through `--env-file`
  and used to construct the provider without inference, copying or displaying the
  key. Authenticated model calls, billed usage and live agent behavior remain to
  be checked in the pilot.
- `study/magic-pilot-config.json` freezes five minutes, 12 attempts, a USD 3
  spending guard, and periodic supervision with reflection. See
  [the launch and monitoring guide](magic-pilot.md) for the exact command,
  exit-code semantics, local trace files, and pilot acceptance checks.

## OpenRouter tool-schema compatibility and live verification

The first live pilot failed before training because Anthropic rejected the
`run_analysis` tool's root-level `allOf`. The provider now sends bounded parameter
alternatives nested inside `params`, while the controller and local worker retain
the original model-specific validation. Traces record the actual transmitted
tool schemas.

- Final full suite: **224 passed in 35.79 seconds**. Compilation and
  `git diff --check` passed. Regression cases cover MAGIC, regression, and legacy
  tool schemas; independent scoped review found no material issue.
- A live validation-only check used the existing Tutorial 3 credential through
  OpenRouter, with `anthropic/claude-sonnet-4.5` pinned to Anthropic. Two model
  calls successfully inspected the project/results and launched one classifier
  trial locally. The run exited successfully at its one-trial cap.
- The local histogram gradient boosting trial achieved validation ROC-AUC
  **0.931693**. OpenRouter reported **USD 0.023874**, with complete accounting:
  5,458 input tokens and 500 output tokens. MAGIC test data was not scored.
- Artifacts are in the ignored directory
  `study-runs/magic-api-schema-check-20261020-145955`. This check verifies the
  API-to-local-worker path; the full five-minute pilot, including live supervisor
  reviews and reflections, remains the next test.

## Live findings panel and read-only watcher

- Full suite: **244 passed in 34.84 seconds**; compilation and whitespace checks
  passed. Tests cover classification/regression direction, target reporting,
  incomplete usage, partial UTF-8 journal writes, background timers, recovery,
  terminal cleanup, quiet/plain/verbose output, and final stdout preservation.
- The default interactive display redraws a compact findings panel and spinner.
  Full scrolling output is opt-in with `--verbose`; complete trace files remain
  unchanged. Plain-text summaries default to 15 seconds between changed views.
  The watcher polls new journal content once per second, independently of the
  local animation. Neither observer makes API calls or feeds content to agents.
- A terminal replay of the real MAGIC trace verified panel redraw and cleanup,
  without repeating inference or training. Independent review found and verified
  fixes for recovered-run termination and clearing the panel before final stdout
  when printed summaries are disabled.
- The user's five-minute run `magic-live-20261020-150222` completed nine local
  trials and reached validation ROC-AUC **0.933147**, with two recorded supervisor
  reviews. It stopped at the deadline. Its final accounting reports
  **USD 0.479454 known**, marked incomplete; this is not a confirmed total charge.
  The watcher exposes that uncertainty rather than estimating missing usage.

## Rich dashboard and automatic local resource allocation

- Full suite: **264 passed in 38.90 seconds**. Compilation, whitespace checks
  and installed dependency compatibility checks passed. Independent review found
  no remaining material issue after fixes for cancellation cleanup and preserving
  training time separately from queue time during recovery and reporting.
- The Rich dashboard adds budget bars, recent experiment outcomes, score trends,
  measured findings and labeled supervisor interpretation. Terminal previews were
  rendered at 120, 80 and 55 columns. Animation and summaries make no API calls.
  `--verbose` retains full scrolling output; logs and structured traces remain.
- `--max-cores N` enables a shared command-local training thread budget, capped
  at logical CPUs, with up to four threads per fit. Suites overlap at most two
  independent runs and their API waits. Nested native thread pools are limited;
  cancellation retains an allocation until worker cleanup completes. Tests cover
  real worker allocation, queue deadlines, budget reuse and isolated run displays.
- An offline MAGIC check completed all **10 trials across five conditions** with
  a six-core ceiling. Recorded allocations were two and four cores, with peak
  combined allocation six. Artifacts are in the ignored directory
  `study-runs/balanced-offline-20261020-152500`. Scripted model responses exercised
  local training without paid inference or scoring the MAGIC test partition.
- Core counts represent allocated training capacity, not sampled OS utilization.
  Separate commands do not share the pool. Queue waiting consumes wall-clock
  allowances but not training time; API guards remain per run. Omission preserves
  the original sequential single-thread policy. Concurrent resource competition
  can affect wall-time comparisons, so keep the policy fixed across conditions.

## Automatic graphical completion reports

- Full suite: **268 passed in 46.52 seconds**; compilation and whitespace checks
  passed. Review verified that interrupted trials mark recorded training time as
  an incomplete subtotal. Tests cover missing durations, unknown outcomes,
  exported figures, automatic reports for successful and failed pilots, and
  preserving nonzero search failure status without scoring test data.
- Single-run CLI completion now writes `report.html`, `summary.csv`, and
  `figures/performance.{png,svg}` / `figures/workflow.{png,svg}`, then includes the
  report path in its final JSON. Existing suite postrun deadlines remain intact.
  Reports use frozen artifacts only, add no API usage, and record rendering time.
- Reports include overview cards, existing performance/attainment/cost/token
  figures, trial-outcome bars and component wall-time totals. Missing and partial
  timing is explicit; sums across concurrent runs are not suite elapsed time.
- Rebuilt reports for `magic-live-20261020-150222` and
  `balanced-offline-20261020-152500`. Inspected the rendered single-run performance
  figure and both workflow figures; fixed axis bounds so unknown durations remain
  visible even when no bar exists. No paid inference or held-out scoring was run.

## Terminal dashboard flicker

- Captured a 100×30 dashboard refresh: inline Rich Live emitted 30 erase-line
  commands before repainting the frame. The dashboard now uses Rich's alternate
  screen, which homes the cursor and overwrites a padded frame. The same probe
  emitted zero erase-line/erase-screen commands on refresh and restored the normal
  screen and cursor on stop. Verbose scrolling logs retain their inline status.
- Full suite: **270 passed in 46.00 seconds**; compilation and whitespace checks
  passed. Regression coverage includes resizing, cancellation cleanup, final output
  preservation, and disabling escape sequences for pipes/plain-text mode. Scoped
  review found no material issue. The user's Termius session was not directly
  inspected; verification targets the reproduced clear-before-redraw behavior.
