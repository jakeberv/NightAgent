# Study operator reference

This reference covers the controlled runner in `study/`. Start with the
[local demonstration](getting-started.md) for a first run. The
[five-arm overnight runbook](five-arm-overnight.md) owns the current paid launch
recipe; the [configuration index](configurations.md) identifies every preset's
comparison, limits and status. Commands below run from the `NightAgent` directory.

The current `apprentice_interactions` suite uses memory in `researcher_alone`,
`frequent`, `periodic` and `periodic_reflection`. Its explicit
`periodic_reflection_no_memory` control matches the fourth arm with memory off.
All supervised arms use Night Science and initial framing; literature is disabled.
Each independent run starts with empty lessons. The
[memory-default contract](memory-default.md) defines this mapping and explicit
opt-out behavior outside it: `--no-lesson-memory` disables memory for `run` and
the earlier `schedules`/`supervisor_strategies` comparisons; `--lesson-memory`
explicitly enables it. These flags do not redefine the fixed five-arm suite.

## Command map

| Task | Command / guide |
| --- | --- |
| Scripted decisions with real local fits | `study smoke --comparison apprentice_interactions --output NEW_DIRECTORY`; [first-run guide](getting-started.md) |
| Create or validate a profile | `study init-problem`, `study validate`; [problem definitions](problem-definitions.md) |
| Freeze data and partitions | `study prepare`; [frozen evaluation](problem-definitions.md#frozen-evaluation-and-extensions) |
| Fit the predeclared local reference | `study reference`; [measured Fashion reference](fixed-reference.md) |
| Launch a paid single condition | `study run`; review a [preset](configurations.md) |
| Launch the current paid comparison | `study suite`; [five-arm runbook](five-arm-overnight.md) |
| Inspect live or saved progress | `study watch --output RUN_DIRECTORY`; [controls](#live-display-and-logs) |
| Freeze an interrupted run | `study recover --output RUN_DIRECTORY`; [recovery](#artifacts-evaluation-and-recovery) |
| Score frozen selections | `study evaluate --data DATA_DIRECTORY --output RUN_OR_SUITE_DIRECTORY`; [held-out rules](#artifacts-evaluation-and-recovery) |
| Rebuild saved reports | `study report --output RUN_OR_SUITE_DIRECTORY`; [interpretation](#reports-and-matched-comparisons) |
| Audit a saved five-arm suite | `study audit --output SUITE_DIRECTORY`; [acceptance](five-arm-overnight.md#reusable-offline-audit) |
| Run developer checks | [CI](ci.md) and [named evaluation cases](evaluation-cases.md) |

Use `.venv/bin/python -m study` in place of `study` in these summaries. `run` and
`suite` use live model calls; an output path containing “smoke” does not make them
offline. The `smoke` subcommand uses scripted models and fixture literature with
real fits and synthetic-data evaluation. It establishes operation rather than
strategy benefit. Use fresh output paths for each new search or engineering
evaluation receipt. For full arguments, use `.venv/bin/python -m study COMMAND --help`.

## Credentials and paid execution

Before paid execution, review the preset, prepare matching data, check key
allowance and billing evidence, and measure a bounded pilot's actual latency and
charged usage. Record funding visibility and the launch decision in
[readiness](workshop-readiness.md). The
corrected memory contract passed [targeted solo-memory revalidation](solo-memory-revalidation.md).
The [preflight recipe](targeted-preflight.md) and
[overnight runbook](five-arm-overnight.md) own current launch requirements.
Earlier costs and memory policies are historical and do not establish a current
estimate.

Supply `OPENROUTER_API_KEY` in the launching environment or pass `--env-file PATH`.
Tutorial-style `LLM_API_KEY` is accepted when that file's `LLM_BASE_URL` identifies
HTTPS OpenRouter. Existing environment credentials take precedence. Files are
parsed as literal assignments without executing shell code; their model/endpoint
settings do not override study configuration. Keep keys out of configuration,
arguments and version control. The [MAGIC guide](magic-pilot.md) includes an
interactive zsh key-entry example.

Live runs require an explicit model ID and provider slug. Reviewed plain
tool-capable models are in `study.provider.REVIEWED_PLAIN_MODELS`. Unknown IDs,
routing aliases, variants and models with built-in search are rejected. Extending
the registry requires reviewing the exact capabilities and adding an acceptance
check. Requests pin provider `only` and `order`, disable fallback and require
parameter support. Account presets must not add implicit retrieval.

The public endpoint/pricing catalogue is snapshotted before search. Charged
`usage.cost` supplies accounting; catalogue prices provide provenance. Raw
responses, request/generation IDs, served model/provider metadata, cache/reasoning
details and failed calls are retained. Missing billing stops execution with
`unknown_cost` by default. The exploratory `allow_unknown_cost: true` override
leaves totals incomplete. Dollar guards check known charges between calls; a
request may exceed a guard, and a timed-out request may incur an unknown charge.
A guard is not a billing ceiling.

The provider owns one total call deadline. It retains generation headers before
reading the JSON body and reserves at most five seconds (10% of shorter limits)
within that same deadline for one generation-receipt lookup when billing is
unknown. Only a matching, finalized receipt supplies actual charges and token
counts. A failed attempt with unresolved cost stops before retry, including when
exploratory unknown-cost execution is enabled. No missing charge is treated as
zero. Cancelled calls retain received evidence and remain cancelled. Receipt
lookups add no inference attempt; their elapsed time counts against the call.

## Problems, prepared data and equivalent trials

The [problem guide](problem-definitions.md) owns profile format, CSV/NPZ input,
classification/regression adapters, objectives, targets and bounded search spaces.
Model/provider and resource limits belong in a separate study configuration.
`run`, `suite` and `reference` infer the prepared directory's frozen profile;
an optional `--problem` must match it. Invalid identities fail before provider
construction or pricing requests. Targets record first crossings and never stop
search. Agents receive training/validation information without test records or
statistics; workers receive only permitted training/validation files.

Prepared data cannot be overwritten with a different source, definition or seed.
Identical preparation verifies fingerprints. Refresh older metadata by rerunning
the same preparation only when no run uses the directory; verified partitions
remain unchanged. Preserve original prepared directories for historical runs that
still need held-out evaluation. Model adapter versions are recorded per run and
are independent of prepared-data identity.

Equivalent successful proposals return the previous observation without fitting
or consuming a trial slot. `experiment_reused` records proposed/matched IDs;
repeated proposals remain bounded by the no-progress limit. Equivalence includes
preprocessing, training seed, data/split, implementation version and objective.
Safe aliases resolve defaults: `sqrt` and `log2`, for example, both select three
random-forest features on ten-feature data. Scaling is never assumed equivalent;
unknown metadata cannot establish an alias. Reuse is not independent replication.
Agents cannot change the fixed training seed within a matched run.

Every arm also receives `completed_configurations`: an execution registry of all
completed effective configurations and seeds, including trials outside recent
history. It shares parameter bases and stores per-configuration differences;
failed fits are excluded. It is available with memory off and contains no lesson
interpretations. `last_reused_proposal` and the reuse count persist across phases.
These fields help agents choose novel comparisons; the equivalence guard still
checks every proposal, and the harness does not choose an alternative. The
42-fit overnight solo history adds about 7.6 kB (47%) to its measured context,
so paid token cost and reduced duplicates need a new operational pilot.

Random forests accept `sqrt`, `log2` or `all` for `max_features`; numeric `1` and
`1.0` are rejected because scikit-learn gives them different meanings. Context
includes actual fitted parameters. Histogram boosting records actual iterations,
the ceiling and early-stopping behavior in `fit_diagnostics`; those observations
alone do not establish underfitting or convergence.

## Evidence, hypotheses and lesson contracts

New runs freeze these policies:

| Policy | Contract |
| --- | --- |
| `structured_v1` | Role-specific decision JSON and validation citations |
| `supervision_v2` | Shared framing and strategy-specific reviews |
| `active_advice_v1` | Framing remains active advice until a later review |
| `grounded_v3` | Measured factual summaries; interpretations retained separately |
| `observed_v1` | Deadline admission using observed call/fit durations |

`run_analysis` requires an `intent`: hypothesis, completed baseline trial ID (or
null), proposed change, expected informative outcome, response to supervisor
advice and reason, short complete-sentence summary, and validation evidence.
Evidence requests contain only `trial_id` and `metric`; supplying `value` or
`split` is rejected. The harness attaches the exact recorded validation value and
split. Stored accepted contracts retain all four fields. Citation validation
checks recorded evidence rather than an interpretation's truth. Stated advice
uptake does not establish that advice caused an improvement.

Supervised arms frame the brief before the first researcher decision. Both styles
share kickoff instructions and framing fields: motivation, hypothesis, assessment,
testable question, recommendation, expected outcome, summary and empty evidence.
Framing has no execution/literature tools; it receives the experiment schema and
resource limits. Its calls/repairs consume normal budgets, and accepted framing
is a separate `framing` event. Invalid framing or exhausted repairs stop before
training. `initial_framing` persists; `last_supervisor_feedback` holds it until
review replaces it. Context identifies `active_advice_source`, and the first
researcher decision must follow, modify or reject the advice with a reason.

Later standard reviews require assessment, unresolved question, recommendation,
expected outcome, summary and evidence. They allow creativity without an explicit
Night Science checklist. Night Science adds:

| Strategy | Required review content |
| --- | --- |
| Explore before judging | Two or three distinct `alternative_explanations` before assessment |
| Reframe stalled work | `motivation` and testable `unresolved_question` within the brief |
| Connect across fields | `cross_field_connection` with a testable implication, or why no useful analogy applies |
| Design an experiment | Bounded recommendation, expected and `falsifying_outcome`, including inconclusive results |
| Check evidence | Assessment tied to completed measurements and limitations |
| Respect limits | `resource_check` covering time/trials, fit timeout, CPU/device and interaction overhead |

Fields allow at most 500 characters; alternatives allow 240 each. Both styles
require a valid citation once completed trials exist; beforehand, empty evidence
is valid. Schema checks cannot establish alternatives' quality, analogy usefulness
or advice feasibility.

Invalid responses return actionable errors within existing turn/review budgets.
Review/reflection repairs disable tools and report up to six concise field errors
with limits. Exhausted repairs stop unsuccessfully; attempts retain raw responses
and usage. A single JSON object wrapped in prose/Markdown may be parsed locally.
Multiple objects, duplicate fields, malformed JSON and invalid citations fail.
No separate model call merely summarizes the interface. Explicit old
`supervisor_policy` values are rejected for new execution; historical formats
are not a compatibility guarantee.

Memory is on by default, including for solo researchers without explicit
reflection. The register holds six lessons by default (`memory_limit`: 1–12),
each with ID, scope, complete-sentence finding, validation citations and status
`supported`, `inconclusive` or `superseded`. Reusing an ID revises it; least
recently updated lessons are evicted at the cap. Memory-enabled responses can
include up to two `lesson_updates`. If the register is empty and a completed fit
has a citable validation measurement, each researcher decision must include
at least one scoped, cited observation note through that existing field. The
first decision, absence of citable completed evidence, and histories with only
failed fits are exempt. A researcher's note is saved when a proposal is admitted
for a new fit. Reused or deadline-skipped proposals do not save it, so an empty
register still requires a note on the next decision. Once the register is
nonempty, further updates are optional. Memory-off behavior is unchanged.

Missing or empty required updates use the existing bounded decision-repair budget
before another fit starts; they add no reflection phase or separate memory call.
A factual observation, including an inconclusive one, suffices. No novel insight
or causal claim is required. Memory survives history truncation and recovery
within a run; `lessons.json` and events preserve it. Independent runs start empty;
other runs' lessons and test feedback are never loaded. `supported` describes generated
factual observations rather than independent replication. Original explanations
remain unverified. The [memory contract](memory-default.md) owns opt-out behavior
and the fixed five-arm mapping.

The harness generates factual summaries/assessments and lesson finding/scope from
completed measurements. `comparison_scope` identifies changed settings and
confounding; raw interpretations remain in lessons and the audit trace.
Hypotheses, analogies and predictions remain explicitly unverified, including
conditional predictions using causal words. These checks are not a semantic truth
checker. Measured `target_status` replaces explicit target-status assertions;
separable target-purpose clauses are removed while retaining experiments. Keep
actions and target commentary in separate sentences. Advisory `capacity_estimate`
includes scheduled calls and observed trial/queue durations; it is unavailable
before timing evidence, may be optimistic, and never changes hard limits/cadence.

Context is rebuilt from recent trials, current best, framing, latest relevant
feedback/reflection and enabled lessons. Repeated fitted configurations, artifact
metadata, epoch-loss arrays and duplicate interpretations are omitted. Measurements,
requested settings, resolved feature counts, actual devices, failures, predictions
and comparison limits remain; full detail stays in logs. Constructor
`effective_config` leaves neural device unresolved; worker
`actual_effective_config` and `fit_diagnostics` record execution. Agents cannot
execute arbitrary code, shell, chosen paths or generated pipelines.

## Limits and shared resources

After framing, order is result → due review → enabled reflection → next researcher
decision. Completed/failed/timed-out attempts count toward cadence and trial caps.
Invalid proposals launch no trial but consume time and can trigger no-progress
stops. No extra treatment call follows a limit that prevents another trial.
Ordinary planning remains available in every arm.

Each model attempt refreshes remaining time/trials and observed average call
latency. `model_start_buffer_seconds` defaults to one second; zero disables the
minimum. `observed_v1` reserves recent observed model and completed-fit durations
plus 25% slack. Reviews/reflections must leave time for another decision and fit.
Fits are checked again after decisions; skipped fits use no trial slot. Maxima
include queue time; new families borrow observed timing until their own exists.
The rule is identical across arms, but observed overhead differs. Runs may stop
early as `deadline`; `model_call_skipped`/`trial_skipped` record remaining/required
time. Estimates cannot guarantee unseen/slower work; hard timeouts still apply.
Unknown charges take precedence over simultaneous deadlines and fail execution
unless explicitly allowed. Valid artifacts remain available.

`--max-cores N` sets a command-wide training-thread ceiling bounded by logical
CPUs, with up to four threads per fit and limited nested pools. Suites overlap
up to two independent runs under the budget; dependent calls stay sequential.
Without a ceiling, execution retains the serial single-thread baseline. MPS fits
are serialized. Queue waiting consumes deadlines but is separate from training
wall time; spending guards remain per run. This is not OS affinity or a ceiling
on other applications/separate commands. Keep resources fixed across comparisons.

Allowances start after provisioning and include calls, retries, tools, reviews,
reflection, retrieval, waits and failures. Trial timeouts cannot exceed remaining
time. Workers use clean environments and bounded numeric-library threads;
process groups are killed/reaped on cancellation/timeout. Artifacts are verified.
Reaching a target does not stop search.

Suites need a future absolute deadline with UTC offset, enough full allowances
at configured concurrency, setup slack and postrun reserve. They reject insufficient
initial windows and never shorten later arms to fit. Unstarted runs remain
visible. `suite.json` freezes order, seeds, configuration, identities, platform,
source/library fingerprints, prices and deadline. After frozen search, evaluation
gets up to 70% of remaining time and reporting the rest, in killable processes
bounded by that deadline. `completion.json` records phases. `--validation-only`
explicitly skips held-out evaluation; a JSON preset alone does not select it.

Search failures, no valid selected model, and failed/timed-out/unstarted postrun
phases exit nonzero. Reporting is attempted after evaluation failure. Normal
deadline/trial/dollar caps with a valid model remain successful search stops.
Standalone `reference`/`evaluate` fail nonzero on fitting/scoring failure.

## Live display and logs

Interactive runs use a Rich dashboard in the alternate terminal screen, restoring
screen/cursor/keyboard settings on exit. Focus is default; Details adds notebooks,
diagnostics, usage and logs. The controls also work in `study watch` and only
affect the display:

| Key / option | Effect | Commands |
| --- | --- | --- |
| `f` | Toggle Focus / Details without Enter | Interactive `run`, `suite`, `smoke`, `watch` |
| `l` | Show/hide Details live log; from Focus, open Details with log | Interactive `run`, `suite`, `smoke`, `watch` |
| `x` | Cycle time, cumulative API-cost and input-plus-output-token axes | Interactive `run`, `suite`, `smoke`, `watch` |
| `[` / `]` | Select concurrent run; selection stays fixed as others advance | Interactive suite display |
| `--verbose` | Full scrolling event log | `run`, `suite`, `smoke` |
| `--no-animation` | Plain-text output | `run`, `suite`, `watch` |
| `--quiet` | Hide live progress; retain durable logs | `run`, `suite`, `smoke` |
| `--summary-interval SECONDS` | Plain summary interval, default 15; zero disables periodic summaries | `run`, `suite` |

Focus shows activity, best objective, next target/gap, progress and latest lesson.
Each dot is a completed scored experiment; the step line shows selected best so
far and dashed lines show targets. Failed/unscored fits have no invented score.
Maximized objectives rise, minimized objectives fall; accuracy/gaps use percent/
percentage points and AUC retains numeric scale. This charts experiments rather
than epoch loss. Bounds expand, nearby points can overlap, and there is no
smoothing, extrapolation or inferred convergence. Cost/token coordinates include
all preceding role usage at completion. Cached/reasoning subsets are not counted
twice; incomplete accounting omits points on that axis with an explicit count.

Details shows actual settings, named-baseline changes, best/prior-best/tied/behind
trials and failures. An absent baseline makes its comparison unavailable.
Summaries are complete attributed sentences; full text stays in evidence. API
waiting shows elapsed time, without completion percentages or private thinking.
Lesson panels show accepted New/Updated/Superseded events with status, source
role and trial IDs, pointing to `lessons.json` when text cannot fit. Unchanged
snapshots are not new learning; memory-off runs have no lesson panel.

The live log shows completed model responses, tools, contracts and usage as
events rather than provider token streaming. It holds at most 2,000 lines /
262,144 characters per run; durable `progress.log`/`events.jsonl` retain history.
Displayed terminal controls are removed. Views use existing events and add no
model calls/tokens. Use roughly 100 columns by 35 rows for the full notebook;
small windows prioritize activity, scores, budgets and warnings. Keyboard input
requires interactive POSIX stdin; Ctrl+C retains normal behavior. Concurrent
histories/accounting stay separate and completed selected runs remain inspectable.

Host CPU samples all applications on the observer machine once per second with
30-sample history, separately from allocated training slots. Initial readings
show `sampling`, failures `unavailable`. In `watch`, utilization describes the
watching machine and allocations describe the recorded run. CPU samples are
transient; queue/allocation evidence stays in traces. Detailed terminal layout
behavior is also described in the [MAGIC guide](magic-pilot.md).

```bash
.venv/bin/python -m study watch --output RUN_DIRECTORY --interval 15
.venv/bin/python -m study watch --output RUN_DIRECTORY --once
```

The watcher exits on a stop event or recovered summary. Progress uses stderr;
the final summary uses stdout. Plain summaries print on changed events at the
configured interval plus a final summary, without model calls.

## Reports and matched comparisons

`study report --output RUN_OR_SUITE_DIRECTORY` reads frozen evidence and
regenerates HTML/exports without providers or held-out scoring. Single `run`
commands generate reports after frozen search, including failed search, and
print their paths. Suites retain postrun phases/reserve. HTML embeds graphics;
keep `figures/` for PNG/SVG download links. `summary.csv` and
`paired-comparisons.json` retain machine-readable results.

The default front page asks how much validation quality each strategy achieves
for model tokens, API USD, and experiment attempts. Its short written summary is
built by deterministic rules over computed results: no LLM calls, strategy names,
conclusions, thresholds, or resource budgets are embedded in those rules.
`report-summary.txt` exports the prose, `research-efficiency.json` exports the
cohorts/calculations/method, `resource-trajectories.json` exports individual
observations and evidence limits, and `report-provenance.json` fingerprints the
loaded evidence. The original outcome, target, operational, role-accounting,
held-out and trace sections remain in expandable supporting evidence. The
presentation does not change declared outcomes or audit acceptance criteria.

Resource cohorts share the existing frozen-identity gate and configuration
strata used for matched outcomes. All scheduled runs in each stratum remain,
including failures and nonattainers. Repeat/seed membership and duplicates are
reported; descriptive group means are not paired effect estimates. Missing or
inconsistent identities are listed explicitly outside the cohorts, not pooled.
For each resource independently, the common lower budget is the latest first
valid-model observation, and the upper budget is the earliest known prefix end
across **every** cohort run. A run with no scored prefix blocks the cohort's
comparison instead of disappearing. No subgroup is selected to extend the
budget, no quality is imputed for a run without a valid model, and no curve is
extended beyond observed resource use. These budgets are exploratory, selected
from resource support rather than outcomes or target attainment.

Absolute quality is the best observed valid in-allowance score at a cumulative
budget. Improvement is direction-aware progress from **each run's own incumbent
at the common lower budget**. The default report assumes no external zero-budget
baseline: initial spending is retained in absolute budgets, and early improvement is not estimated. The baseline may
differ across strategies and across resource axes; more subsequent improvement
does not necessarily mean higher quality. Both start and end quality are
exported alongside improvement. Continuous improvement area uses the exact
right-continuous step integral; budget-normalized AUC divides by the shared
interval width, retaining native metric units (no automatic percentages,
score-range scaling, or cross-task pooling). Experiment AUC uses the discrete
sum after attempts `start+1` through `end`, divided by `end-start`. Endpoint jumps
therefore contribute to discrete AUC but not continuous area. The report
withholds AUC if there is no positive shared interval.

Resource coordinates come from serial controller journals. All roles, retries,
reviews, reflection, failed calls and spending without a fit count. Input plus
output tokens excludes double-counting cached/reasoning subsets. Trial starts
count admitted experiments, including failed, timed-out, late and unfinished
attempts; only observed valid results improve quality. Reused proposals are not
new experiments. Unknown token or dollar usage ends that axis's known prefix
independently, even if later usage is known; it never becomes zero. Missing or
corrupt journals, inconsistent starts and accounting disagreements are explicit
evidence limits. Complete accounting snapshots are checked against reconstructed
usage. Local compute and post-run work remain separate from API USD. SDs describe
observed repeats and do not establish superiority or uncertainty across tasks.
Fewer total trials alone never establishes fewer trials required for a result.

To regenerate a historical experiment without changing its evidence or report:

```bash
python -m study report --output study-runs/EXISTING_SUITE \
  --report-dir study-runs/NEW_REPORT_DIRECTORY
```

The optional `generate_report(source, destination=...)` API uses the same loading,
analysis and atomic rendering pipeline. With a separate destination, the source
`postrun.json` is also untouched. The default automated invocation keeps writing
to its existing report location.

Reports include every planned run, no-classifier outcomes, stop reasons,
validation progress, attainment, trial outcomes and per-role requests, failed/
cancelled/unfinished attempts, retries, known cost/token subtotals and resource
times. Missing accounting stays unknown. Model, local-fit and queue times are
separate; concurrent component totals are neither suite elapsed time nor
CPU-seconds. Uptake, invalid contracts, repeated calls and reused experiments
remain descriptive evidence rather than causal advice-quality estimates.

Matching requires the same frozen problem/data/objective, allowance, repeat and
training seed. Only declared treatments may differ. Other configuration,
protocol and memory differences stay separate; duplicate units and unknown
identities are excluded. Tables retain counts, unmatched runs and pairs lacking
scores. Differences use complete pairs and B minus A; consult metric direction.
Memory is `periodic_reflection` minus `periodic_reflection_no_memory` (on minus off).

With at least two complete pairs, a two-sided 95% Student-t interval describes
mean paired differences. These exploratory intervals assume independent repeats
and approximately normal differences, are unstable with small samples and have
no multiple-comparison adjustment. Repeats on one frozen split do not measure
uncertainty across new datasets or resampled splits.

Target reports combine reached/not-reached fractions with measured crossing
cost/tokens/time. Nonattainers stay censored at observed budgets; crossing and
convergence costs are never invented. Successful-run means are conditional and
cannot rank efficiency alone. Compare attainment and final validation together;
held-out scores are separate confirmation. API USD excludes hardware/electricity.
A scripted fixture or one live repeat cannot establish a strategy winner.

## Artifacts, evaluation and recovery

The [event format](event-format.md) owns journal versions and strict audit,
interrupted-append recovery and report-warning policies. Unsupported versions
fail explicitly. Historical layouts are not translated into current evidence
and may require their original checkout.

Runs save append-only `events.jsonl`, frozen `config.json`, agent-facing
`project.json`, live `checkpoint.json`, `progress.log`, verified model artifacts
and final `summary.json`; enabled memory adds `lessons.json`. Completed valid
trials update best; ties keep the earliest completed trial. Named targets have
separate first-crossing selections with time/accounting. Late, incomplete and
unsuccessful trials cannot update selections.

Held-out evaluation uses frozen selections and untouched test data. A shared
artifact-hash cache scores identical artifacts once. Durable reservations precede
scoring; an interrupted reservation becomes `uncertain` and is never scored
again. Test results stay outside agent contexts; there is no test-driven retuning
or qualitative model judge. The [fixed reference](fixed-reference.md) is outside
the five adaptive treatments.

Run directories cannot be reused for more search. After a crash, freeze each
interrupted run, rebuild the suite report, then audit:

```bash
.venv/bin/python -m study recover --output SUITE_DIRECTORY/runs/RUN_ID
.venv/bin/python -m study report --output SUITE_DIRECTORY
.venv/bin/python -m study audit --output SUITE_DIRECTORY
```

Recovery freezes committed results as `interrupted`, granting no new time, fits
or paid calls. In-flight billing stays unknown. Reports reconcile the frozen
schedule even with missing summaries; recover those runs to finalize observed
accounting. Incomplete work can still fail acceptance. A report's existence does
not establish acceptance; use the [five-arm audit rules](five-arm-overnight.md#reusable-offline-audit).

## Earlier experiment recipes

These workflows address earlier study questions and do not select the current
protocol. Runnable presets now default memory on; historical runs retain their
original settings. Consult the [preset index](configurations.md) before adapting
a recipe, and use the [current runbook](five-arm-overnight.md) for the demo.

### Legacy MAGIC workflow and feasibility pilot

The profile-backed [MAGIC pilot](magic-pilot.md) is the maintained short recipe.
The older `--csv` interface expects headerless UCI `magic04.data`: ten numeric
features and final `g`/`h` labels (`g` positive). It freezes stratified 60/20/20
partitions, row IDs and SHA-256 identities:

```bash
.venv/bin/python -m study prepare \
  --csv study-data/magic-source/magic04.data --seed 42 --output study-data/magic
.venv/bin/python -m study reference \
  --data study-data/magic --output study-runs/fixed-reference --timeout 60
```

Download the source from [UCI MAGIC](https://archive.ics.uci.edu/dataset/159/magic+gamma+telescope).
Legacy data without a profile uses a fixed histogram-boosting reference and
validation AUC; profiles use their adapter's reference/metrics. MAGIC, a fixed
holdout and the model menu were feasibility choices. Grouped/temporal/cross-
validation tasks need a suitable trusted evaluator.

A validation-only local check on 20 October 2026 used seed 42, the
11,412 / 3,804 / 3,804 split and one worker thread:

| Predeclared candidate | Validation ROC-AUC | Complete worker wall seconds |
| --- | ---: | ---: |
| Fixed HGB reference | 0.940256 | 1.458 |
| Logistic regression, standard scaling | 0.837075 | 1.213 |
| Random forest, 200 trees | 0.941238 | 6.100 |
| HGB, 100 iterations | 0.938881 | 1.449 |
| HGB, 400 iterations | 0.939278 | 1.673 |

Times include startup, preprocessing, fitting, validation and persistence. This
reached 0.93 but did not demonstrate 0.95, with no test scoring or model calls.
Machine-local evidence is in ignored `study-runs/magic-pilot/`; runtime varies.

### Earlier Fashion supervisor-style pilot

The earlier paid five-minute validation-only design uses
`study/fashion-five-minute-config.json`: researcher alone, frequent standard and
frequent Night Science supervision. Each arm has 105 seconds, 12 attempts and a
$1 guard; two waves plus a 45-second reporting reserve fit its five-minute window:

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

The [Fashion guide](fashion-pilot.md) owns preparation, MPS calibration and the
earlier three-arm overnight recipe. Current data uses accuracy targets
0.85/0.88/0.90 and `study-data/fashion-mnist`; `fashion-pilot` data belongs to
earlier targets. Runnable three-arm presets now use memory throughout;
`--no-lesson-memory` opts out. Earlier memory-off records do not validate this
change. For the current protocol use the [targeted preflight](targeted-preflight.md).
The [comprehensive smoke](comprehensive-smoke.md) is a separate earlier **paid**
coverage recipe. The [revised preflight](revised-preflight-results.md) recorded
35 fits, 65 calls and $1.665021 on 21 October 2026, with a **NO-GO** from failed
solo-memory coverage. That historical receipt remains unchanged. The contract
correction passed a [bounded paid revalidation of the failed solo arm](solo-memory-revalidation.md):
seven fits and seven calls for $0.163809, with zero audit errors or warnings.
The other four arms were not rerun; this is no combined current-source five-arm
pass or evidence of strategy benefit.

### Three-condition supervisor comparison

`comparison: "supervisor_strategies"`, or `suite --comparison supervisor_strategies`,
selects the earlier review-style design:

| Arm | Review | Framing | Reflection / literature |
| --- | --- | --- | --- |
| `researcher_alone` | None | None | Disabled |
| `standard_supervisor` | Every attempt | Shared kickoff | Disabled |
| `night_science_supervisor` | Every attempt | Shared kickoff | Disabled |

Repeats share seed, model, data, limits and base memory; order is randomized.
Review prompts/contracts differ, so token usage and fit counts may differ within
budgets. Reports give all three matched contrasts. This compares complete review
strategies rather than equal-length prompt variants. Offline verification:

```bash
.venv/bin/python -m study smoke --comparison supervisor_strategies \
  --output study-runs/supervisor-comparison-smoke
```

For a paid suite use `study/supervisor-comparison-config.json`, prepared data,
credentials, `--repeats`, a future `--deadline` with UTC offset and
`--reserve-seconds`. Allow three full allowances per repeat at chosen concurrency
plus reserve. Add `--validation-only --repeats 1` for an operational pilot.
A single standard run uses `--condition frequent --supervisor-strategy standard`.
This suite includes both styles regardless of the base style setting.

### Earlier five-schedule comparison

`comparison: "schedules"` remains the runner/config default unless overridden.
Select `apprentice_interactions` explicitly for the current demo. These earlier
schedules hold base memory and supervisor style fixed:

| Condition | Review | Explicit reflection | Literature |
| --- | --- | --- | --- |
| `researcher_alone` | None | No | No |
| `frequent` | Every attempt | No | No |
| `periodic` | Every three attempts | No | No |
| `periodic_reflection` | Every three attempts | Between trials | No |
| `periodic_reflection_literature` | Every three attempts | Between trials | Scheduled supervisor reviews only |

Use the [MAGIC all-five recipe](magic-pilot.md#all-five-strategies) for a paid
validation-only pilot. `study/pilot-config.json` is the original 15-minute general
baseline, not a calibrated current overnight preset. A suite repeats five
schedules with matched incrementing seeds and randomized arm order. Plan five
full allowances per repeat at chosen concurrency plus setup/postrun reserve.

Only the final schedule exposes literature tools during reviews. A fixed cap
counts search/fetch attempts; Crossref search needs no key. Fetch allows bounded
public text/HTML/XML/JSON, rejects PDFs, compressed/private responses, and allows
five redirects within the original timeout. Each hop receives destination
validation and IP pinning. URLs/chains, absent abstracts and failed/unhelpful
queries remain in evidence. Traces link query/evidence, feedback, researcher
response and trial ID. Retrieval is disabled in `apprentice_interactions`.

### Design provenance and historical records

The [shared experimental design](https://docs.google.com/document/d/1tBVSIyVEs3PdngYK7uHr1yEs5l3R0f5kC1OOjMMFqqA/edit?tab=t.60m8hjogcisp)
reflects the current protocol alongside the [specification](../SPEC.md),
[protocol guide](workshop-protocol.md) and [memory contract](memory-default.md).

The [retrieved source snapshot](experimental-design-source.txt) and
[20 October implementation plan](plans/2026-10-20-overnight-study.md) preserve
earlier stages, including superseded three-condition memory proposals and
six-analysis budgets. [Tutorial attribution](tutorial-attribution.md) records
adaptations. The [saved real replay](evidence/fashion-demo/demo.md) is historical
mechanism evidence from the former memory policy.
