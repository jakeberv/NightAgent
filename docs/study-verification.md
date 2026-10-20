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

The final study dataset/protocol, model/provider, repeats, run allowance, and
secondary caps remain explicit pilot choices. The implementation and synthetic
smoke do not establish that any interaction strategy is superior.
