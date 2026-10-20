# Controlled overnight comparison

This runner implements the **Experimental design** tab dated 20 October 2026,
using direct OpenRouter Chat Completions and bounded classifier tools. It is
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

## Prepare the task and pilot it

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

## Configure OpenRouter

Copy `study/pilot-config.json` and review it before a live pilot. It is an
illustrative 15-minute allowance, not a calibrated final overnight schedule.
Supply `OPENROUTER_API_KEY` in the launching process's environment; the study
runner does not load `.env` automatically. Keep the key out of configuration,
arguments, and version control.

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
HTML, XML, and JSON; PDFs, redirects, compressed responses and private destinations
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
timeout and remaining run time. Neither 0.93 nor 0.95 ends search.

The suite refuses a window too small for the initial schedule and never
shortens a later condition to fit. Unstarted planned runs remain visible,
and incomplete comparisons are explicitly flagged. After search, evaluation
gets up to 70% of remaining time and reporting the rest. Both run in killable
processes bounded by the study deadline. `completion.json` records postrun
success, failure, or timeout.

## Artifacts, evaluation, and recovery

Each run has an append-only `events.jsonl`, `config.json`, agent-facing
`project.json`, live `checkpoint.json`, verified model artifacts, and final
`summary.json`. Every completed valid trial can update the best checkpoint.
Ties retain the earliest completed trial. First milestone and first stretch
crossings have separate selections with elapsed time and cumulative accounting.
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

Reports lead with best completed validation ROC-AUC at the common deadline,
include every planned run and explicit no-classifier outcomes, and carry
early-stop curves forward to the allowance. Nonattainers have unknown crossing
time, never an invented deadline crossing. Attainment curves, held-out test
checks, tokens, charged/lower-bound dollars and training wall seconds are
reported separately. Cached and reasoning tokens are subsets, not extra tokens.
Post-search local evaluation/reporting compute is metered separately.
