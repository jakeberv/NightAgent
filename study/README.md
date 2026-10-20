# Controlled overnight comparison

This runner implements the **Experimental design** tab dated 20 October 2026,
using direct OpenRouter Chat Completions and bounded scientific tools. It is
separate from the conversational Claude SDK prototype in `nightagent/run.py`.
The older `SPEC.md` three-condition design and its six-analysis budget do not
govern this runner.

[Source design](https://docs.google.com/document/d/1tBVSIyVEs3PdngYK7uHr1yEs5l3R0f5kC1OOjMMFqqA/edit?tab=t.60m8hjogcisp)
· [Retrieved source](../docs/experimental-design-source.txt)
· [Tutorial adaptations](../docs/tutorial-attribution.md)
· [Implementation plan](../docs/plans/2026-10-20-overnight-study.md)

## Setup and offline verification

Use Python 3.12 or later from the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-study.lock
.venv/bin/python -m pytest -q
.venv/bin/python -m study smoke --output study-runs/offline-smoke
```

`requirements-study.lock` records the verified dependency versions;
`requirements-study.txt` contains the supported dependency ranges for updates.

The smoke command uses synthetic data, scripted model decisions, and fixture
literature responses. It trains real classifiers, runs all five schedules,
evaluates saved selections, and produces `report.html` and `summary.csv`.
It makes no API or literature requests. Its curves verify the workflow and
are not evidence comparing language-model strategies.

## Define a problem and pilot it

The runner accepts YAML/JSON problem profiles specifying the question, dataset,
split, objective, named targets, and bounded model search space. Classification
and regression are supported. Model/provider and resource limits remain in a
separate study configuration.

See the [problem profile guide](../docs/problem-definitions.md) for CSV/NPZ input,
custom targets such as AUC 0.95, and the MAGIC, multiclass CSV, MNIST, and regression
examples. MNIST uses macro one-vs-rest ROC-AUC, retains accuracy as a secondary
metric, and preserves its official test partition.

```bash
.venv/bin/python -m study validate --problem study/problems/regression.yaml
.venv/bin/python -m study smoke --problem study/problems/regression.yaml \
  --output study-runs/regression-smoke
.venv/bin/python -m study prepare --problem study/problems/magic.yaml \
  --output study-data/magic-profile-v2
```

The MAGIC command requires the source downloaded to the path below. Pass the
prepared directory to `run`, `suite`, or `reference`; they infer its frozen profile.
An optional `--problem` must match it. Invalid or changed definitions fail before
provider construction. Targets record first crossings and never stop search.

### Legacy MAGIC workflow and feasibility pilot

Download the headerless `magic04.data` from the
[official UCI MAGIC Gamma Telescope dataset](https://archive.ics.uci.edu/dataset/159/magic+gamma+telescope).
Preparation expects ten numerical features and a final `g`/`h` label.
`g` is the positive class. It creates fixed stratified 60/20/20 training,
validation, and test partitions with row IDs and SHA-256 fingerprints:

```bash
.venv/bin/python -m study prepare \
  --csv study-data/magic-source/magic04.data --seed 42 --output study-data/magic
.venv/bin/python -m study reference \
  --data study-data/magic --output study-runs/fixed-reference --timeout 60
```

Prepared data cannot be overwritten with a different source or seed. Reusing
it verifies fingerprints. Agents receive feature names, train/validation counts,
and the classifier schema; neither test records nor test statistics are exposed.
The reference is a fixed histogram gradient boosting configuration, outside
the five experimental conditions. `reference` reports validation AUC only.

MAGIC, one fixed holdout validation partition, and the bounded classifier menu
are **pilot choices**. The implementation does not assert that they are the final
study protocol. Grouped, temporal, or cross-validation protocols require a new
trusted evaluator before using a dataset that needs them.

A validation-only local pilot on 20 October 2026 used the exact seed-42
11,412 / 3,804 / 3,804 partition and one worker thread:

| Predeclared candidate | Validation ROC-AUC | Complete worker wall seconds |
|---|---:|---:|
| Fixed HGB reference | 0.940256 | 1.458 |
| Logistic regression, standard scaling | 0.837075 | 1.213 |
| Random forest, 200 trees | 0.941238 | 6.100 |
| HGB, 100 iterations | 0.938881 | 1.449 |
| HGB, 400 iterations | 0.939278 | 1.673 |

These timings include worker startup, preprocessing, fitting, validation,
and artifact persistence. This pilot reached 0.93 but did not demonstrate 0.95.
No test labels were evaluated and no language model was called. The local
ignored `study-runs/magic-pilot` directory contains the predeclared configurations,
environment, hashes, reproduction script, and results. Runtime varies by host.

## Evidence, hypotheses, and run-local lessons

New runs use the `structured_v1` decision protocol. `run_analysis` requires an
`intent` object containing a hypothesis, completed baseline trial ID (or null),
change, expected informative outcome, supervisor response and reason, a short
complete-sentence summary, and validation evidence. Supervisor and reflection
responses use role-specific JSON contracts. The harness verifies each cited trial,
metric, validation split and exact measurement before accepting it. These checks
verify recorded evidence, not the truth of a model's interpretation. A supervisor
response records stated uptake; it does not prove advice caused an improvement.

Invalid contracts return actionable errors and consume the existing bounded
turn/review budget. Exhausted repairs stop unsuccessfully; they cannot silently
become valid feedback. All attempts retain usage and raw responses. There is no
extra model call just to summarize the interface. The contract does add bounded
input/output tokens to existing requests; all are included in normal accounting.
Old JSON config files adopt the new protocol automatically. Protocol identity is
frozen in every new run; reports label old logs as legacy for comparison purposes.

Each API attempt refreshes the remaining time, remaining trial count and observed
average call latency. Review/reflection format repairs disable further tool calls
and report up to six concise field errors with explicit character limits. A frozen
`model_start_buffer_seconds` setting (default 1 second; zero disables it) prevents
starting a request with less than that much time left. Such a stop is recorded as
`deadline`, with a `model_call_skipped` event explaining the buffer; it incurs no
call charge. In-flight calls still obey the hard deadline and may leave unknown
charges if cancelled. The buffer does not predict latency or guarantee completion.

Effective-configuration diagnostics resolve constructor defaults and safe aliases.
For example, `sqrt` and `log2` both select three random-forest features on a ten-feature
dataset. Equivalent successful trials generate an advisory warning, visible in the
trace, interface, and subsequent agent context. The requested trial still runs.
Preprocessing, training seed, data/split, implementation version and objective are
part of equivalence; scaling is never assumed interchangeable. Unknown metadata
cannot establish an alias equivalence. Changing seeds still requires a separate
run with its seed recorded, rather than letting the agent alter a matched study.
Completed histogram-gradient-boosting trials also report actual iterations,
the iteration ceiling and early-stopping behavior in `fit_diagnostics`. These
observations reach the agents, preventing confusion between a requested maximum
and the number of iterations actually trained. They do not establish underfitting
or convergence. Prompts require claims to stay scoped to tested settings and the
current split; citation validation alone cannot guarantee sound interpretation.

Add `--lesson-memory` to `run`, `suite`, or `smoke` to enable a bounded lesson
register. It holds six lessons by default (`memory_limit`, from 1 to 12), each with
an ID, scope, complete-sentence finding, validation citations, and status:
`supported`, `inconclusive`, or `superseded`. Reusing an ID revises that lesson;
least recently updated entries are evicted at the cap. Up to two updates may be
included in an existing agent response. Memory starts empty for every run, survives
the recent-trial context window, and is saved in `lessons.json` and the event log.
No other run's memory or test feedback is loaded. Supported is an agent assessment
of cited observations, not a claim of independent replication.

New runs record `reasoning_policy=grounded_v1`. A conservative local wording
check replaces recognizable claims of optimality, performance ceilings, causality,
invariance, and similar overclaims with a complete-sentence summary of their cited
validation measurements. Flagged lessons become `inconclusive` (or remain
`superseded`). Grounded text reaches the UI, feedback, and run-local memory;
original responses and `contract_grounded` adjustments stay in the audit logs.
This is a lexical guard, not a semantic truth checker: uncaught interpretations
still require review. Hypothesis and uncertainty fields remain explicitly tentative.
These adjustments need no model call; necessary schema/citation repairs still do.
Review responses containing a single JSON object inside a prose or Markdown wrapper
are parsed locally. Multiple objects, duplicate fields, malformed JSON, and invalid
citations still fail validation. Reports separate the new policy from older runs.

Random forests now accept `max_features` values `sqrt`, `log2`, or `all`.
`all` explicitly selects every feature; numeric `1` and `1.0` are rejected to avoid
their different scikit-learn meanings. Actual fitted parameters are included in
agent context. Adapter version 2 requires a new prepared directory; the MAGIC
pilot uses `study-data/magic-profile-v2`. Previous artifacts remain unchanged.

Memory is **off by default** and recorded as a separate experimental variant.
`--no-lesson-memory` overrides a config that enables it. A memory-enabled suite
applies the same memory setting independently to all five schedules; it is a
separate suite, not a sixth condition mixed into the original comparison. Review
cadence remains fixed. No RL training, adaptive scheduling, or extra agent roles
are introduced.

The offline demonstration exercises the same contracts with real local fits:

```bash
.venv/bin/python -m study smoke --lesson-memory --quiet \
  --output "study-runs/workshop-smoke-$(date +%Y%m%d-%H%M%S)"
```

## Coordination and matched-comparison reports

Reports add per-role request counts, failed/cancelled/unfinished attempts, retry
counts, known cost and token subtotals, and model wall time. Missing accounting
stays unknown. Cached and reasoning tokens remain subsets, never added a second
time. Time charts separate API calls from local training and queue time. The
report records self-reported advice uptake, invalid contracts, repeated tool
calls and equivalent experiments. Observed score changes are descriptive rather
than causal estimates of advice quality.

Matched comparisons require the same frozen problem, data, objective, allowance,
configuration, repeat and training seed, allowing only condition to vary within a
pair. Protocol and memory variants are not pooled. Duplicate units and unknown
identities are excluded explicitly. Tables retain all-run counts, stop reasons,
unmatched runs and matched pairs missing a valid score. Numerical differences use
complete pairs and are always condition B minus A; consult metric direction.
For two or more complete pairs, the report gives a two-sided 95% Student-t interval
for the mean paired difference; with fewer pairs, no interval is produced. These
exploratory intervals assume independent repeats and approximately normal paired
differences, are unstable with small samples, and are not adjusted for multiple
comparisons. Repeats share the frozen dataset split, so they do not measure
uncertainty across new datasets or resampled splits.

`report.html` embeds the graphics; `figures/roles.svg` and `figures/roles.png` expose
role charts, and `paired-comparisons.json` preserves matched analysis details.
Regenerating a report reads frozen artifacts and makes no model requests:

```bash
.venv/bin/python -m study report --output RUN_DIRECTORY
```

## Configure OpenRouter

For a bounded first run, follow the [short MAGIC pilot](../docs/magic-pilot.md).
Its separate `study/magic-pilot-config.json` uses five minutes, 12 attempts,
a USD 3 guard, and periodic supervision with reflection.

Live runs default to a responsive Rich dashboard in the alternate terminal screen,
overwriting frames without a clear-before-redraw pass to reduce flicker. The normal
screen and cursor are restored on exit. It includes a spinner, budget bars,
best-result card, recent trials, score-history charts, findings, targets and usage.
The research-lab header highlights the actual active role. At 100 columns or wider,
each role has a distinct ASCII robot avatar; only a busy role animates. API waiting
has no invented completion percentage. Disabled roles are labeled for the run's
condition. With at least 76 columns and 33 terminal rows, an experiment notebook
shows the latest trial's actual settings, changes versus the agent's named completed
baseline, and its complete-sentence summary labeled **Agent interpretation**.
When the named baseline is outside the bounded display history, the view says that
the comparison is unavailable instead of substituting another trial. More space reveals the four avatar
stations; use a 100-column, 35-row window or larger for a demo.
Measured discoveries announce new bests, ties, targets and unsuccessful trials,
with a brief sparkle for improvements and target crossings. The connected trial
trail uses `★` for the current best, `↑` for a prior record, `=` for a current tie,
`×` for unsuccessful and `·` for other completed trials. The recent-experiment
table labels **Best now**, **Prior best**, **Tied best**, or **Behind**, and shows
the score gap to the current leader (smaller is closer, for both maximization and
minimization). Failed/unscored/pending trials retain explicit statuses and no gap.
Historical record-setting events remain intact in the trace.
Compact windows prioritize activity, scores, budgets and findings.
All lab state comes from recorded events, adding no model calls or token usage;
full rationale and configuration remain in the trace. New runs supply a short, validated summary within the existing agent response.
Historical logs use complete sentences; if none fit, the notebook describes the
recorded configuration change in a complete sentence. It never clips commentary in the middle of a sentence.
Press **`f`** (no Enter) to toggle **Focus** and **Details** during a live run or
`study watch`. Details remains the default. Focus uses one panel, one active
avatar, the best score and target status, the latest discovery and experiment,
and remaining time, API spending and CPU allocation. Its narrative shows the
recorded agent hypothesis, proposed change and expected result in complete
sentences, separately from measured validation scores. Recorded supervisor
advice or reflection stays visible while the researcher considers the next
experiment, with its source and trial number. Pending calls explain the role's
purpose and show elapsed time for that call (reset on retry); they do not claim
to stream the model's private thinking. When space is tight, explanations take
priority over avatars and CPU detail. Long hypotheses fall back to the recorded
short summary when it fits. This puts activity, results and constraints ahead
of diagnostics; histories, token totals and the four-role
map remain one keypress away in Details. The panel is capped at 96 columns to
keep text readable on wide screens. Smaller windows drop whole low-priority
blocks rather than cut sentences. Known-cost warnings and unsuccessful trial
counts remain visible; the view does not estimate model thinking progress.
The shortcut appears in the panel border when keyboard input is available.
Switches reuse the same screen and do not change experiments, logs or API usage.
When lesson memory is enabled, **Focus includes the latest lesson**, labeled
New, Updated or Superseded, its agent-assigned status, source role and supporting
trial IDs. **Details includes a Lessons notebook**, newest revisions first, with
scope when it fits. Unchanged snapshots do not count as new learning; evicted
lessons leave the display and a new run starts empty. Only accepted memory events
enter the notebook. Lessons are agent interpretations, not verified conclusions.
The view uses complete sentences and points to `lessons.json` when a sentence or
the rest of the notebook cannot fit. Tiny Details windows retain the compact
status view; Focus remains available with `f`. Waiting memory shows an empty state;
disabled memory adds no panel. Existing events drive both live runs and replay in
`study watch`, with no added API calls or tokens.
Keyboard input requires interactive POSIX stdin (macOS/Linux); redirected input,
plain-text and verbose modes remain untouched. Ctrl+C keeps its normal behavior,
and keyboard settings are restored when the display closes.

The default dashboard includes a **Live log** box that follows the full readable
log as events arrive. Wide terminals (132 columns or more) place it beside the
overview; other terminals place it below. Very small terminals retain the compact
status view. Long messages wrap and the viewport follows the newest lines. Press
**`l`** to hide or restore the box; from Focus, `l` returns to Details with the log
visible. **`f`** still toggles the clean Focus view, which hides the raw log.
The box also works in `study watch`. It uses the same full event formatting as
`progress.log`, including model responses, tool output, contract checks and usage.
Model text appears when a provider call completes; this is live event output,
not token-by-token provider streaming. It makes no additional API calls and adds
no model tokens. The display keeps at most 2,000 lines / 262,144 characters per run in memory;
`progress.log` and `events.jsonl` retain the full durable history. Log text is shown
literally with terminal controls removed, and screen redraws retain the existing
Termius flicker protections.

`--verbose` enables the full scrolling log;
`--no-animation` uses plain text and `--quiet` hides all progress. Plain-text
summaries print every 15 seconds when events change, plus a final summary.
Adjust with `--summary-interval SECONDS` (0 disables printed summaries).
Summaries reuse existing results and labeled supervisor commentary, without extra
API calls or feedback into the agents. Detailed traces are always saved.
Attach to an existing single run from a second terminal with
`.venv/bin/python -m study watch --output RUN_DIRECTORY --interval 15`.
Use `--once` for a snapshot; the watcher exits on a stop event or recovered summary.

Add `--max-cores N` to `run` or `suite` to set a command-wide local training
thread ceiling. The runner automatically grants up to four threads per fit,
bounded by available capacity and logical CPUs, and prevents nested native
thread pools from multiplying the allocation. A suite also overlaps up to two
independent runs, sharing that budget while API requests wait. Dependent agent
calls within each run remain sequential. The dashboard separately shows allocated
training slots and actual **Host CPU** utilization (all applications on the local
machine), measured once per second with a 30-sample history on a fixed 0–100%
scale. Sampling makes no API calls and is disabled for non-graphical output.
The first reading is `sampling`; failed readings are `unavailable`, not zero.
The same display works without `--max-cores`, using the serial allocation count.
In `watch`, host measurements describe the observer machine; allocations describe
the recorded run. Host measurements are transient display data;
traces preserve queue duration and allocation. Waiting counts against deadlines
but not training wall time. API spending limits remain per run. Without a
configured ceiling, execution retains the sequential single-thread baseline.
This is a training thread budget, not OS CPU affinity or a cross-command limit.
Keep the resource policy fixed across comparisons. See the
[pilot guide](../docs/magic-pilot.md) for the launch command and details.

Copy `study/pilot-config.json` and review it before a live pilot. It is an
illustrative 15-minute allowance, not a calibrated final overnight schedule.
Supply `OPENROUTER_API_KEY` in the launching process's environment, or pass
`--env-file PATH` to read it from a local file. Tutorial-style `LLM_API_KEY` is
accepted when that file's `LLM_BASE_URL` identifies HTTPS OpenRouter. Existing
environment credentials take precedence. Env files are parsed without executing
shell code; their model/endpoint settings do not override the study configuration.
Keep the key itself out of configuration, arguments, and version control.

Use an explicit model ID and provider slug. Reviewed plain tool-capable models
are listed in `provider.REVIEWED_PLAIN_MODELS`; unknown IDs, routing aliases,
variants, and models with built-in search are rejected. Before extending this
registry, review the exact model's capabilities and add an acceptance test.
The request pins provider `only` and `order`, disables fallback, and requires
parameter support. Do not use account presets that enable implicit retrieval.

The public endpoint/pricing catalogue is snapshotted before search. Actual
charged `usage.cost` is the accounting source; catalogue prices are provenance,
not a substitute estimate. Raw responses, generation/request IDs, served
model/provider metadata, cache/reasoning details, and failed calls are retained.
No live inference was needed for implementation verification.

```bash
.venv/bin/python -m study run \
  --config study/pilot-config.json --condition periodic_reflection \
  --data study-data/magic --output study-runs/live-pilot
.venv/bin/python -m study evaluate \
  --data study-data/magic --output study-runs/live-pilot
.venv/bin/python -m study report --output study-runs/live-pilot
```

`run` is a paid, single-condition pilot. Pilot call latency, actual costs,
literature availability and secondary caps before freezing an overnight
comparison. The dollar and trial limits should rarely bind. Missing billing
stops the run by default with `unknown_cost`; the exploratory
`allow_unknown_cost: true` override keeps totals explicitly incomplete.
The dollar guard checks known charges between calls; a completed request can
cross the ceiling, and timed-out requests may still incur an unknown charge.

## Five controlled schedules

| Condition | Supervisor review | Separate reflection | Literature |
|---|---|---|---|
| `researcher_alone` | None | No | No |
| `frequent` | After every trial attempt | No | No |
| `periodic` | After every three attempts | No | No |
| `periodic_reflection` | After every three attempts | Between trials | No |
| `periodic_reflection_literature` | After every three attempts | Between trials | Supervisor only, during review |

There is no kickoff review. A completed, failed, or timed-out classifier attempt
counts toward cadence and the trial cap. Invalid tool/schema requests do not
launch a trial; they consume time and can trigger the no-progress stop.
The order is result → due review → enabled reflection → next researcher decision.
No extra treatment call is made after a cap/deadline prevents a next trial.
Ordinary planning remains available in every condition.

Every supervisor uses the same Night Science prompt and requested feedback
fields. The researcher alone can invoke `run_analysis`; the supervisor can
inspect the project and results. Literature tools exist only during the fifth
condition's scheduled reviews. A fixed cap counts both search and fetch attempts.
Search uses Crossref without an API key. Fetch accepts bounded public text,
HTML, XML, and JSON. Up to five redirects share the original timeout; each hop
gets fresh destination validation and IP pinning. Original/final URLs and the
redirect chain are retained. PDFs, compressed responses and private destinations
are rejected. Search abstracts can be absent; failed or unhelpful searches are
retained. Trace records link query/evidence, feedback, researcher response,
and the resulting trial ID.

Memory is rebuilt from the same bounded recent-trial window, current best,
and latest condition-specific feedback/reflection on every call. It never
resets because a review occurred. Each run starts fresh. No arbitrary code,
shell, agent-chosen paths, or generated pipelines are executed.

## Overnight suite

Use an absolute deadline with a UTC offset and enough room for all full
allowances, preparation overhead, and the reporting reserve:

```bash
.venv/bin/python -m study suite \
  --config study/pilot-config.json --repeats 5 \
  --data study-data/magic --output study-runs/comparison \
  --deadline 2026-10-21T08:00:00-04:00 --reserve-seconds 3600
```

Change the example date to the intended future deadline. The runner executes
one condition at a time and randomizes condition order within each repeat.
All conditions in a repeat share the same split and training seed; repeat
seeds increment from the configured base. `suite.json` freezes the order,
settings, data/library/source fingerprints, platform, prices, and deadline.
Run the comparison on an otherwise consistent host.

The run allowance starts after provisioning and covers all model/tool calls,
retries, reviews, reflection, literature, waiting and failed attempts. Trial
workers have a clean environment and one-thread numeric libraries; process
groups are killed/reaped on cancellation or timeout. Completed artifacts are
verified before acceptance. The trial limit is the smaller of its configured
timeout and remaining run time. Reaching any declared target does not end search.

The suite refuses a window too small for the initial schedule and never
shortens a later condition to fit. Unstarted planned runs remain visible,
and incomplete comparisons are explicitly flagged. After search, evaluation
gets up to 70% of remaining time and reporting the rest. Both run in killable
processes bounded by the study deadline. `completion.json` records postrun
success, failure, or timeout.

For operational pilots, add `--validation-only --repeats 1` to run all five
strategies and generate the combined report without held-out scoring. The frozen
suite manifest records this policy and `completion.json` labels evaluation
`skipped_validation_only`. Failed searches or reporting still exit nonzero.
See the [all-strategy pilot command](../docs/magic-pilot.md#all-five-strategies).

The CLI exits nonzero for failed search runs, runs without a valid selected model,
and failed, timed-out or unstarted postrun phases. It preserves diagnostics and
attempts reporting even when evaluation fails. Normal deadline/trial/dollar caps
with a valid model remain successful stops. Standalone `reference` and `evaluate`
also exit nonzero on fitting or scoring failure. See the
[pilot guide](../docs/magic-pilot.md) for status interpretation.

## Artifacts, evaluation, and recovery

Each run has an append-only `events.jsonl`, `config.json`, agent-facing
`project.json`, live `checkpoint.json`, verified model artifacts, and final
`summary.json`. The default live panel shows activity, findings and
cumulative usage on stderr; `--verbose` shows the full scrolling event log and
`--quiet` suppresses terminal progress. A readable `progress.log` is saved even
in quiet mode, alongside the complete JSONL trace. Each model-attempt event
includes cumulative accounting; cached/reasoning subsets and unknown totals
remain explicit. Every completed valid trial can update the best checkpoint.
Ties retain the earliest completed trial. First crossings of every named target
have separate selections with elapsed time and cumulative accounting.
Late or incomplete trials cannot update selections.

Evaluation uses only frozen selections and the untouched test partition.
The suite shares an artifact-hash cache, so an identical artifact selected
multiple times is scored once. A durable reservation precedes scoring; a crash
in that interval becomes `uncertain` and is never scored again. Test results
are separate from all agent contexts. There is no test-driven retuning or
qualitative LLM judge.

Existing run directories are never reused for more search. After a crash:

```bash
.venv/bin/python -m study recover --output study-runs/comparison/runs/RUN_ID
.venv/bin/python -m study report --output study-runs/comparison
```

Recovery freezes committed results as `interrupted`; it does not renew the
clock, rerun in-flight trials, or spend more API credits. An in-flight model
request has unknown billing. The report reconciles the frozen schedule even
when some runs lack summaries; recover those runs to finalize accounting.

Reports lead with the best completed validation objective at the common deadline
(ROC-AUC for legacy MAGIC),
include every planned run and explicit no-classifier outcomes, and carry
early-stop curves forward to the allowance. Nonattainers have unknown crossing
time, never an invented deadline crossing. Attainment curves, held-out test
checks, tokens, charged/lower-bound dollars and training wall seconds are
reported separately. Cached and reasoning tokens are subsets, not extra tokens.
Post-search local evaluation/reporting compute is metered separately.
Single `run` commands now automatically write the graphical report after search
and print its path in the final JSON, including when a frozen search failed.
This step reads saved results without evaluating test data or making API calls.
Suites retain their existing post-search evaluation/reporting phases and reserve.
The report includes overview cards, performance/attainment/cost/token charts,
trial-outcome bars and recorded model/local-trial/queue time. Incomplete durations
are marked as subtotals; unknown values stay unknown. Component times summed
across concurrent runs are not suite elapsed time or CPU-seconds. Embedded charts
make `report.html` self-contained; `figures/performance.{png,svg}` and
`figures/workflow.{png,svg}` provide downloadable exports. Keep that folder with
the report if you want the download links to work. Use `study report --output`
to regenerate these outputs for earlier runs or after held-out evaluation.
Reports reject comparisons with different frozen problems, objectives, or dataset
fingerprints. Historical groups with no recorded dataset identity remain readable,
but cannot be pooled with runs having known identity.
