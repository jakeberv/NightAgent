# Controlled study runner

This application uses direct OpenRouter Chat Completions and bounded scientific
tools. The **current demo** is the [five-arm overnight Fashion-MNIST comparison](../docs/five-arm-overnight.md):
researcher alone, frequent supervision, periodic supervision, periodic supervision
plus reflection, and periodic supervision plus reflection and run-local lesson
memory. All supervised arms use Night Science; literature is disabled. Use
[`fashion-five-arm-overnight-config.json`](fashion-five-arm-overnight-config.json)
with the linked recipe's three repeats, resource policy, deadline and `--audit`.
The [preset index](../docs/configurations.md) lists every configuration, its actual
comparison mode, budgets and status.

The earlier five-schedule literature and three-arm supervisor-style comparisons
remain available below. This runner is separate from the
[conversational Claude SDK prototype](../nightagent/README.md) in `nightagent/run.py`.
The older `SPEC.md` three-condition memory design and six-analysis budget are
historical proposals, not this application's protocol.

[Source design](https://docs.google.com/document/d/1tBVSIyVEs3PdngYK7uHr1yEs5l3R0f5kC1OOjMMFqqA/edit?tab=t.60m8hjogcisp)
· [Retrieved source](../docs/experimental-design-source.txt)
· [Tutorial adaptations](../docs/tutorial-attribution.md)
· [Implementation plan](../docs/plans/2026-10-20-overnight-study.md)

## Setup and offline verification

Use the verified Python 3.12 environment from the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-study.lock
.venv/bin/python -m pytest -q
.venv/bin/python -m study smoke --output study-runs/offline-smoke
```

`requirements-study.lock` records the base versions verified on macOS arm64;
`requirements-study.txt` contains supported dependency ranges for updates.
For the pinned Linux CPU neural environment, use
[`requirements-study-cpu.lock`](../requirements-study-cpu.lock) and the
[CI installation command](../docs/ci.md). MPS setup uses the separate
[`requirements-gpu.lock`](../requirements-gpu.lock); see [GPU setup](../docs/fashion-pilot.md).
Neither neural lock is a universal platform lock.

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
  --output study-data/magic-profile
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

New runs freeze `supervisor_policy=supervision_v2`, `supervisor_strategy`
(`standard` or `night_science`, default `night_science`), and the `comparison`
selection. In supervised
conditions, the supervisor frames the brief before the first researcher decision.
The accepted framing stays in `initial_framing` throughout the run, while
`last_supervisor_feedback` holds that framing until a later review replaces it.
New runs freeze `context_policy=active_advice_v1` and expose `active_advice_source`;
initial framing remains active advice on every attempt before the first review.
The first researcher decision
must state whether it follows, modifies, or rejects that advice, with a reason.

Both strategies use identical kickoff instructions and the same framing contract:
motivation, hypothesis, assessment, testable question, recommendation, expected
outcome, summary, and empty evidence. Later **standard** reviews use the earlier
compact format: assessment, unresolved question, recommendation, expected outcome,
summary, and evidence. Standard supervision can reason creatively but is not
instructed to apply the Night Science checklist.

Later **Night Science** reviews additionally make all six strategies observable:

| Strategy | Required review content |
|---|---|
| Explore before judging | Two or three distinct `alternative_explanations`, followed by `assessment`. |
| Reframe stalled work | `motivation` and a testable `unresolved_question`; explain revisions within the fixed brief. |
| Connect across fields | `cross_field_connection` with a testable implication, or an explanation of why no useful analogy applies. |
| Design an experiment | A bounded `recommendation`, `expected_outcome`, and `falsifying_outcome`, including what an inconclusive result means. |
| Check evidence | `assessment` relates the recommendation to cited completed measurements and their limitations. |
| Respect limits | `resource_check` accounts for remaining trials/time, fit timeout, CPU/device constraints, and model/review overhead. |

Fields are concise prose (at most 500 characters; alternatives at most 240 each).
The harness requires the Night Science fields and distinct alternative strings
only for that review strategy. Both strategies require at least one
valid trial citation once completed trials exist. Before any completed trial,
an empty evidence list is valid. Schema and citation checks do not establish the
quality of the alternatives, usefulness of an analogy, or feasibility of advice;
those remain questions for trace review and empirical evaluation.

Framing has no execution or literature tools. The supervisor receives the permitted
experiment schema and current resource limits in context. Its call and repairs
consume the same wall-time and API cost allowance as later work. Invalid framing
or exhausted budgets stop the run before training. Accepted framing is recorded
as a separate `framing` event and appears in the live narrative and report trace.
The frozen policy identifies the review contract. Historical artifacts document
their original policies and are not evidence for the current protocol.

Invalid contracts return actionable errors and consume the existing bounded
turn/review budget. Exhausted repairs stop unsuccessfully; they cannot silently
become valid feedback. All attempts retain usage and raw responses. There is no
extra model call just to summarize the interface. The contract does add bounded
input/output tokens to existing requests; all are included in normal accounting.
JSON config files without an explicit policy adopt the new protocol automatically.
An explicit old `supervisor_policy` is rejected for new execution; remove that
setting only when intentionally starting a new run with the current policy.
Protocol identity is frozen in every new run; historical formats are not a
compatibility guarantee.

Each API attempt refreshes the remaining time, remaining trial count and observed
average call latency. Review/reflection format repairs disable further tool calls
and report up to six concise field errors with explicit character limits. A frozen
`model_start_buffer_seconds` setting (default 1 second; zero disables this minimum)
sets the cold-start floor. The frozen `deadline_policy=observed_v1` additionally
reserves recent observed call and completed-fit durations plus 25% slack. A review
or reflection must leave time for a researcher decision and another fit. Fits are
checked again after the decision returns; a skipped fit consumes no trial slot.
Recent maxima include queue time; a new model family uses other observed fits
until its own timing exists. The rule is identical across comparison arms, but
their observed overhead differs. A run may therefore finish before its allowance.
Stops remain `deadline`; `model_call_skipped` and `trial_skipped` record remaining
and required seconds. These estimates cannot guarantee completion of unseen or
slower work. Hard timeouts still apply. Unknown API charges take precedence over
a simultaneous deadline and make the command fail unless `allow_unknown_cost`
was explicitly enabled; valid models and the report remain available.

### Earlier Fashion supervisor-style pilot

This earlier five-minute, validation-only recipe compares researcher alone,
standard supervision and Night Science supervision on the prepared Fashion-MNIST
subset. For the current three-repeat demo, use the
[five-arm overnight recipe](../docs/five-arm-overnight.md) and its 600-second
per-run allowance and $75 sum of API guards.

The active profile uses 0.85, 0.88 and 0.90 accuracy targets. Prepare it once with
`.venv/bin/python -m study prepare --problem study/problems/fashion-mnist.yaml --output study-data/fashion-mnist`.
The previous `fashion-pilot` directory remains bound to its earlier targets and
must not be used with this updated definition. The partitions and model bounds
are unchanged.

For coverage of both supervisor styles, all five schedules, and memory off/on,
use the [comprehensive smoke recipe](../docs/comprehensive-smoke.md). Its four
validation-only suites contain 20 runs with four attempts each and $40 in combined
API guards; it includes a required event-level coverage audit before longer runs.

The current demo's `--audit` verifies interaction coverage and artifacts after
reporting; `study audit --output ROOT` reruns the offline check independently.
It writes `audit-summary.json` without making model calls or evaluating data.

For the smaller demo comparison, use the [targeted five-arm preflight](../docs/targeted-preflight.md)
and `study/fashion-targeted-preflight-config.json`: researcher alone, frequent
supervision, periodic supervision, periodic plus reflection, and periodic plus
reflection and memory. Its `apprentice_interactions` mode fixes Night Science style,
disables literature, and reports only the four adjacent contrasts, including the
explicit memory contrast. Other frozen configuration differences remain separate.

```bash
.venv/bin/python -m study suite \
  --config study/fashion-five-minute-config.json \
  --env-file ../AgenticAI2026_Tutorial-3/.env \
  --problem study/problems/fashion-mnist.yaml --data study-data/fashion-mnist \
  --device mps --max-cores 4 --repeats 1 --validation-only \
  --reserve-seconds 45 \
  --deadline "$(.venv/bin/python -c 'from datetime import datetime,timedelta; print((datetime.now().astimezone()+timedelta(minutes=5)).isoformat())')" \
  --output "study-runs/fashion-five-minute-$(date +%Y%m%d-%H%M%S)"
```

This allows 105 seconds per arm in two waves, with 45 seconds reserved for reporting
and approximately 45 seconds of startup/scheduling slack. Each arm has a $1 spending
guard and a 12-trial safety cap (raised from six to avoid premature pilot stops).
An in-flight call may exceed the dollar guard. Lesson memory is off for all arms.
The pilot checks operation and initial efficiency; use multiple matched repeats
and a higher trial cap for overnight comparisons. Keep the prepared data and
search space fixed across arms; the held-out test set is untouched by this command.

Effective-configuration diagnostics resolve constructor defaults and safe aliases.
For example, `sqrt` and `log2` both select three random-forest features on a ten-feature
dataset. Equivalent successful trials return the previous observation without fitting or
consuming a trial slot. The `experiment_reused` event records the proposal and
matched trial IDs; the agent must choose another configuration. Repeated proposals
are bounded by the no-progress limit and do not establish independent replication.
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
No other run's memory or test feedback is loaded. Supported describes the generated factual observations, not a claim of independent
replication. Original agent explanations remain explicitly unverified interpretations.

New runs record `reasoning_policy=grounded_v3`; reports keep earlier policies in
separate analysis groups. The runner resolves evidence from completed trial IDs
and metric names. Factual review/reflection summaries and assessments are generated
from those measurements; `comparison_scope` identifies changed settings and
confounding. Lesson findings and scope are also generated, while raw interpretations
remain in the audit log and `lessons.json`. Hypotheses, analogies and predicted
outcomes are explicitly unverified; a conditional prediction is not erased merely
because it uses a causal word. This is not a semantic truth checker.

Each refreshed context includes `target_status` (reached/pending, first crossing and
remaining gap) and `capacity_estimate`. Explicit target-status assertions are replaced locally with measured status.
Separable target-purpose clauses are removed from actions, retaining the experiment.
Predictions and hypotheses remain unverified even when they mention targets; the
computed target_status is authoritative. Keep an
experiment action in a separate sentence from target commentary so both can survive
normalization. The estimate includes pending and scheduled researcher, review and
reflection calls plus observed local trial/queue duration. It is unavailable before
timing evidence exists, advisory only, and may be optimistic when tools, repairs,
retries or workloads change; it never changes the hard limits or review schedule.

Agent context omits repeated constructor/fitted configurations, artifact metadata,
epoch loss arrays and duplicated lesson interpretations. Scientific measurements,
requested settings, resolved feature counts, actual training/inference devices,
failures, predictions and comparison limits remain. Full records stay in the logs.
Constructor `effective_config` omits the unresolved neural device; worker
`actual_effective_config` and `fit_diagnostics` record actual execution. These
adjustments need no model calls; necessary schema/citation repairs still do.
Review responses containing a single JSON object inside a prose or Markdown wrapper
are parsed locally. Multiple objects, duplicate fields, malformed JSON, and invalid
citations still fail validation. Reports separate the new policy from older runs.

Random forests now accept `max_features` values `sqrt`, `log2`, or `all`.
`all` explicitly selects every feature; numeric `1` and `1.0` are rejected to avoid
their different scikit-learn meanings. Actual fitted parameters are included in
agent context. Prepared data is independent of the model adapter version, so
model-code fixes reuse `study-data/magic-profile`. Each run records the current
adapter version in its project metadata. Re-running the `prepare` command above
refreshes older metadata in place after verifying the source, problem, split,
and partition hashes; it never rewrites the saved partitions. The refreshed data
fingerprint includes partition hashes and excludes the adapter version. Historical
run artifacts keep their original fingerprints and should retain their original
prepared directory if later held-out evaluation is needed. Do not refresh a data
directory while a run is using it. A genuinely changed source or problem still
requires a separate prepared directory.

Memory is **off by default**. In `schedules` and `supervisor_strategies`,
`--lesson-memory`/`--no-lesson-memory` selects the same memory setting independently
for every arm; reports keep those variants separate. In `apprentice_interactions`,
suite construction fixes memory off for the first four arms and on for the final
arm, so the final adjacent contrast explicitly tests memory. Review cadence stays
fixed. No model-weight training or adaptive treatment scheduling is introduced.

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
repeat and training seed. Only the selected comparison's declared treatment
fields may differ: schedule, supervisor style, or the final five-arm memory
contrast. Other configuration, protocol and memory differences are not pooled.
Duplicate units and unknown identities are excluded explicitly. Tables retain all-run counts, stop reasons,
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
screen and cursor are restored on exit. Focus is the default; Details adds budget
bars, a best-result card, recent trials, diagnostics and usage.
The Details research-lab header highlights the actual active role. At 100 columns or wider,
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
**Focus is the default interactive view.** Press **`f`** (no Enter) to toggle
Focus and Details during a live run or `study watch`. Focus puts the activity,
best validation score, next target and gap above a live **experiment progress**
chart. Each completed, scored trial adds a dot at its completion time. A step
line shows the selected best so far, record-setting dots have distinct markers,
and dashed lines show configured targets. Failed and unscored trials add no
score; unsuccessful counts and failure messages remain visible.

The chart uses the configured validation objective: accuracy/AUC rises when it
improves; a minimization objective falls. This shows search progress across
experiments, not epochs or training loss. Accuracy and its target gap are shown
as percentages and percentage points; AUC retains its numeric scale. The progress
sentence describes observed improvements or the number of trials without one;
it never claims convergence.

Press **`x`** to cycle the horizontal axis: elapsed time, cumulative API cost,
and cumulative input + output tokens. Coordinates are snapshots at trial
completion, including all earlier researcher/reviewer/reflection calls in that
run. Cached and reasoning token subsets are not added twice. Missing/incomplete
accounting omits that trial from the relevant axis and displays the omitted
count; it never becomes a zero-cost point. Time uses the run allowance and cost
the spending guard as initial bounds. Token bounds grow in powers of two.
Vertical bounds are labelled and expand when needed, never shrink during a run.
All completed observations are retained; close points may share a terminal cell,
where record-setting points take precedence. There is no smoothing or extrapolation.

Concurrent runs keep independent histories and accounting. The selected run stays
fixed when other runs emit events or finish. Press **`[`** / **`]`** to select the
previous/next run; the border identifies the run and its position. A completed
selected run remains inspectable while other runs continue. All-run completion
restores normal terminal output. These keys change only the display.

Recorded agent hypotheses, supervisor advice and reflection remain attributed
complete sentences. Pending calls explain the role's purpose and show elapsed
time for that call (reset on retry); they do not stream private model thinking.
Focus retains the latest lesson, time/cost limits and unsuccessful trial count.
On small screens, whole secondary blocks and then the chart are removed before
critical figures and warnings; the graph requires at least 60 columns and 23 rows.
The panel is capped at 96 columns. Details retains the table, notebook, diagnostics
and a larger chart when space permits. Markers and axis labels work without color;
non-UTF-8 output uses ASCII plot marks. Plot content is cached between result events,
and view changes reuse the alternate screen to retain Termius flicker protections.
All of this is local, with no additional model calls or tokens.

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

Details includes a **Live log** box that follows the full readable
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

## Earlier five-schedule comparison

| Condition | Supervisor review | Separate reflection | Literature |
|---|---|---|---|
| `researcher_alone` | None | No | No |
| `frequent` | After every trial attempt | No | No |
| `periodic` | After every three attempts | No | No |
| `periodic_reflection` | After every three attempts | Between trials | No |
| `periodic_reflection_literature` | After every three attempts | Between trials | Supervisor only, during review |

All four supervised conditions start with one framing step; `researcher_alone`
starts directly with the researcher. A completed, failed, or timed-out classifier attempt
counts toward cadence and the trial cap. Invalid tool/schema requests do not
launch a trial; they consume time and can trigger the no-progress stop.
After framing, the order is result → due review → enabled reflection → next researcher decision.
No extra treatment call is made after a cap/deadline prevents a next trial.
Ordinary planning remains available in every condition.

These schedules belong to `comparison: "schedules"`; the current five-arm demo
replaces the literature arm with a memory contrast. The selected
`supervisor_strategy` applies across these five schedules. The
researcher alone can invoke `run_analysis`; the supervisor can
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
initial framing, and latest condition-specific feedback/reflection on every call. It never
resets because a review occurred. Each run starts fresh. No arbitrary code,
shell, agent-chosen paths, or generated pipelines are executed.

## Overnight suite

### Three-condition supervisor comparison

Use `comparison: "supervisor_strategies"` in the config, or pass
`--comparison supervisor_strategies` to `suite`. The supplied
[`supervisor-comparison-config.json`](supervisor-comparison-config.json) retains
the pilot's model and budget defaults and selects these arms:

| Arm | Review schedule | Framing | Reflection / literature |
|---|---|---|---|
| `researcher_alone` | None | None | Disabled |
| `standard_supervisor` | After every attempt | Shared kickoff | Disabled |
| `night_science_supervisor` | After every attempt | Shared kickoff | Disabled |

The runner randomizes the three arms within each repeat, gives them the same
training seed, model, data, tools, limits, and memory setting, and stores unique
run IDs plus each arm's strategy in the manifest. A requested run window must
fit **three** full allowances per repeat (subject to configured concurrency),
plus the reporting reserve. The standard and Night Science arms differ in their
review prompt and response contract; actual token usage and experiment counts
can differ within the matched budgets. This tests the complete review strategy,
not a token-for-token prompt ablation.

Verify the workflow without API or literature calls:

```bash
.venv/bin/python -m study smoke --comparison supervisor_strategies \
  --output study-runs/supervisor-comparison-smoke
```

Launch a paid comparison after configuring the model/provider and preparing data:

```bash
.venv/bin/python -m study suite \
  --config study/supervisor-comparison-config.json \
  --data study-data/magic --output study-runs/supervisor-comparison \
  --repeats 5 --deadline 2026-10-21T08:00:00-04:00 --reserve-seconds 3600
```

Adjust the example deadline to a future time. Add `--validation-only --repeats 1`
for an operational pilot without held-out scoring. Reports retain all three arms,
including missing/unstarted runs, and compute all three pairwise comparisons
using matched seeds/repeats. Only the intended strategy field is ignored for
matching; other configuration differences still prevent pairing.

For a single supervised run, select `--condition frequent --supervisor-strategy
standard`. For the original five-schedule suite, use `comparison: "schedules"`
(the default) and select either supervisor strategy. The three-arm preset always
includes both strategies regardless of the base config's strategy selection.

### Five-schedule comparison

Use an absolute deadline with a UTC offset and enough room for all full
allowances, preparation overhead, and the reporting reserve:

```bash
.venv/bin/python -m study suite \
  --config study/pilot-config.json --repeats 5 \
  --data study-data/magic --output study-runs/comparison \
  --deadline 2026-10-21T08:00:00-04:00 --reserve-seconds 3600
```

Change the example date to the intended future deadline. The runner randomizes
condition order within each repeat. Without `max_cores`,
it executes one run at a time; with a shared core pool, it balances up to two
concurrent runs and permits one MPS fit at a time.
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

The [event format and read policies](../docs/event-format.md) define the versioned
journal contract, strict audit parsing, interrupted-append recovery and visible
report corruption warnings. Unsupported versions are explicit errors; historical
layouts are not translated into current evidence.

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
fingerprints. Missing dataset identity cannot establish a matched comparison.
Historical artifacts may require their original checkout; obsolete event formats are not
translated into current-format evidence.


### Fashion-MNIST and strategy efficiency

See [the calibrated Fashion-MNIST pilot](../docs/fashion-pilot.md) for optional
PyTorch installation, local no-API calibration, a short MPS pilot, and a five-strategy
validation-only comparison. `--device mps` requires a working Apple GPU; `auto`
selects MPS when available, otherwise CPU. Classical estimators stay on CPU.
Neural profiles require PyTorch before a paid run can begin.

Target reports include reached/not-reached counts, measured first-attainment
cost/tokens/time, and all-run attainment curves. Unreached targets stay censored at
the observed budget; unknown accounting is not zero. Conditional successful-run
means alone do not rank strategy efficiency. One pilot repeat is not a statistical
comparison. All report calculations are local and require no extra model calls.

Model evidence requests now contain only `trial_id` and `metric`; the harness
attaches the exact recorded `value` and validation `split`. Supplying either
measurement field in a request is rejected. Stored contracts retain all four
fields for audit, and lessons retain unverified interpretations separately.

See [continuous integration](../docs/ci.md) for the CPU GitHub Actions checks and local GPU validation boundary.
