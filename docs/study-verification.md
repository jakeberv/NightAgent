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
