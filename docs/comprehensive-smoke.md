# Comprehensive strategy smoke

Prepared 2026-10-20. This checks live workflow coverage on the frozen Fashion-MNIST
problem; it is not a study of strategy superiority. The paid smoke is not launched
by preparing this recipe.

## Coverage and limits

Run four suites: standard and Night Science supervision, each with lesson memory
off and on. Every suite includes researcher alone, frequent supervision, periodic
supervision, periodic supervision with reflection, and periodic supervision with
reflection and literature. Both styles therefore exercise every supervised
schedule. Night Science uses its six practices together, not six separate arms.

One matched repeat per suite produces **20 runs / 18 distinct treatments**:
researcher alone has no supervisor style, so its memory-off and memory-on controls
are each repeated across the style suites. Do not count these as independent
matched repeats or pool them to inflate evidence. Memory starts empty in each run;
the training seed is 42 throughout. Suite order is fixed for reproducible smoke
diagnosis; arm order within each suite is randomized with seed 2026.

Each run permits **four attempts, 300 seconds, and a $2 API guard**. Four attempts
allow a periodic review after attempt three to inform attempt four. Time/cost
limits can stop a run sooner; coverage must be checked in logs. Across all suites,
the guards sum to **$40**, with possible final in-flight-call overrun. Four shared
CPU cores permit two concurrent runs per suite, with serialized MPS fits. Three
five-minute waves per suite give at most about **60 minutes of search**; each suite
gets a 20-minute window including a three-minute reporting reserve and slack.
Suites run sequentially, so reserve up to roughly 80 minutes plus provider setup.
Actual runtime may be much shorter when four attempts finish quickly.

The prepared data, model bounds, model/provider, 85%/88%/90% targets, and hardware
policy match the existing Fashion comparison. All suites are validation-only;
official held-out test labels are not scored. This does not sweep other datasets,
model providers, CPU-only execution, or individual Night Science practices.

## Launch from the NightAgent repository

The following command makes paid OpenRouter calls and public literature requests.
It uses the existing credential file without printing it. Run the entire block in
Bash. Failure stops the remaining suites and preserves all existing artifacts.
Use a fresh output root on rerun; never overwrite an earlier smoke.

```bash
set -euo pipefail
smoke_root="study-runs/fashion-comprehensive-smoke-$(date +%Y%m%d-%H%M%S)"
mkdir "$smoke_root"
for strategy in standard night_science; do
  for memory in off on; do
    memory_flag=--no-lesson-memory
    if [ "$memory" = on ]; then memory_flag=--lesson-memory; fi
    deadline="$(.venv/bin/python -c 'from datetime import datetime,timedelta; print((datetime.now().astimezone()+timedelta(minutes=20)).isoformat())')"
    .venv/bin/python -m study suite \
      --config study/fashion-comprehensive-smoke-config.json \
      --env-file ../AgenticAI2026_Tutorial-3/.env \
      --problem study/problems/fashion-mnist.yaml \
      --data study-data/fashion-mnist \
      --supervisor-strategy "$strategy" "$memory_flag" \
      --repeats 1 --order-seed 2026 --validation-only \
      --reserve-seconds 180 --deadline "$deadline" --no-animation \
      --output "$smoke_root/$strategy-memory-$memory"
  done
done
```

## Acceptance audit

An exit code of zero alone is insufficient. Inspect each suite's `completion.json`,
each run's `summary.json` and `events.jsonl`, and its generated `report.html`.

- All 20 runs started, produced a valid classifier, and have complete token/cost
  accounting. All accepted artifacts have matching hashes; no unexpected API,
  contract, fit, or report failures occurred.
- Frequent runs have accepted post-trial reviews. Every periodic run has an
  accepted review after attempt three followed by a fourth attempted fit. If a
  guard prevents this, mark that path **not exercised**, not passed.
- Reflection-enabled runs have accepted reflection events followed by another
  researcher decision. Disabled schedules have no explicit reflection events.
- Each literature-enabled run has a successful live search and fetch, plus valid
  subsequent review evidence. Tools are optional model choices: an enabled tool
  that was never invoked is **not exercised**. Search with no usable results does
  not verify fetch; diagnose or do a targeted follow-up instead of claiming coverage.
  Non-literature conditions must not invoke literature tools.
- Memory-on runs contain accepted lesson updates and a later decision receiving
  those lessons. Memory-off runs have no lesson-memory events. Verify no lessons
  carry between runs.
- All six Night Science fields appear in accepted Night Science reviews. Standard
  reviews use their own contract. Field presence verifies structure, not reasoning
  quality or the independent benefit of a practice.
- Held-out evaluation is recorded as skipped; no new test-results files appear.
  Unreached targets remain nonattainment with null conditional attainment costs.

Keep the four reports separate: the existing reports deliberately do not pool
memory/protocol variants. Summarize coverage across them before approving a longer
experiment. Coverage failures should receive targeted diagnosis; do not increase
all budgets or launch the full study automatically.

## Preparation verification — 2026-10-20

The four-suite offline matrix passed: **20 runs, 80 successful classifier fits**,
with expected review cadence, explicit reflection, memory events, fixture literature
search routing, complete accounting, matching saved artifact hashes, and no held-out
scoring. Reports were generated for all four suites. These checks used synthetic
data, CPU classifiers, scripted model responses and fixture literature; they do not
verify live search/fetch, live provider behavior, MPS, or scientific effectiveness.
The frozen Fashion-MNIST profile and prepared data passed preflight separately.

The existing suite and supervisor-strategy tests passed: **28 tests in 28.46s**.
The launch block passed Bash syntax validation; the configuration, treatment count,
budget arithmetic and per-suite time window were checked. No paid calls were made.

Local verification artifacts (gitignored):
`study-runs/comprehensive-offline-20261020-212950/coverage.json`, four suite reports,
and `verification.py`, a copy of the offline verification script. To reproduce from
the repository root, run
`PYTHONPATH=. .venv/bin/python study-runs/comprehensive-offline-20261020-212950/verification.py`.
It creates a fresh timestamped offline output directory.

## Live smoke and review — 2026-10-20

The user-authorized paid run completed at
`study-runs/fashion-comprehensive-smoke-20261020-213448`. All four suites exited
successfully: **20 runs, 80 successful fits (73 MPS, seven CPU), 184 API calls,
989,992 input/output tokens, $3.839736**. Suite runtimes totalled 946.49 seconds
(about 16 minutes, excluding setup). All runs stopped at the four-attempt cap.
Accounting was complete, all model artifact hashes and recorded source hashes
verified, all reports completed, and held-out scoring was skipped. Review cadence,
reflection followed by decisions, and Night Science review fields were verified.

**Execution passed; comprehensive acceptance did not.** Resolve these findings
before treating this as validation of the full study:

- **Advice-context ambiguity:** 38 researcher responses used `not_applicable`
  while initial framing was present and `last_supervisor_feedback` was null.
  This affected all 12 periodic runs. The model explicitly interpreted the null
  field as absence of advice; validation correctly rejected the response. Make
  active advice explicit and clarify that initial framing remains applicable until
  replaced. Recheck periodic runs after the change; do not relax the validator.
- **Literature not exercised:** none of the four literature-enabled runs searched
  or fetched. A separate, no-LLM diagnostic using the same client returned five
  Crossref results and successfully fetched publisher text (2,628 characters).
  This verifies the service, not agent retrieval or evidence use. Add a targeted
  check that actually retrieves and uses evidence, clearly separated from the
  optional-use experimental policy.
- **Researcher-only memory not exercised:** both memory-enabled researcher-only
  controls emitted no lesson updates. All eight supervised memory runs started
  empty, saved lessons, and delivered them to later researcher calls. Add a
  targeted researcher-only memory check before claiming that path is validated.
- **One additional recovered citation error:** a Night Science supervisor cited
  `fit_diagnostics` as a metric. The evidence contract accepts numeric metrics;
  validation rejected it. Clarify allowed metric names in context/repair feedback.

All 39 rejected responses recovered; their recorded API charges totalled
**$0.825258**, affecting 13 runs. There were no API transport failures or classifier
failures. No deadline/dollar stops occurred, so these logs add no coverage for
those paths. One repeat and optional features that went unused cannot establish
strategy superiority. No implementation fixes or longer experiment were launched.

Detailed local evidence: `review-summary.json`, `audit.json`,
`literature-service-probe.json`, `console.log`, four `report.html` files, and the
raw per-run `events.jsonl` files under the run root above. The launcher and audit
scripts are preserved there as well.
