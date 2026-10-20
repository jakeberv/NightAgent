# Short MAGIC pilot

This is an operational check of authenticated tool calls, completed classifier
trials, supervisor feedback, reflection, and charged usage. It does not establish
which strategy performs best. The 12-trial cap makes this a fixed-experiment-count
operational pilot whenever all strategies reach it. For a wall-time comparison,
raise the cap so the equal time allowances bind, and keep that choice frozen
across strategies.

The prepared configuration is `study/magic-pilot-config.json`:

- Condition: `periodic_reflection`, with supervisor review after three attempts.
- Model/provider: `anthropic/claude-sonnet-4.5` / `anthropic`, without fallback.
- Limits: five minutes, 12 trial attempts, 60 seconds per trial and model call.
- Spending guard: USD 3 per run; missing billing stops the run. This guard checks
  charges between requests, so the last request can exceed it.
- Dataset: `study-data/magic-profile`, frozen from `study/problems/magic.yaml`;
  binary ROC-AUC with validation targets 0.93 and 0.95.

Run these commands from the NightAgent repository root. The existing `.venv`
must contain the dependencies in `requirements-study.lock`, and the UCI source
must be at `study-data/magic-source/magic04.data`.

```bash
.venv/bin/python -m study prepare \
  --problem study/problems/magic.yaml --output study-data/magic-profile
```

Preparation verifies existing data and refreshes older metadata in place. Model
adapter versions are recorded per run, so code fixes no longer require a new data
directory. Refreshing verifies the source, problem, split and partition hashes;
it leaves all saved partition files unchanged. Run this command only after any
active pilot using the directory has stopped. Preserve the original prepared
directory for historical runs that still need held-out evaluation, because their
saved artifacts retain the old data fingerprint.

The launch command below reads the existing Tutorial 3 `.env` using `--env-file`.
It accepts `OPENROUTER_API_KEY`, or the tutorial's `LLM_API_KEY` when
`LLM_BASE_URL` identifies HTTPS OpenRouter. Only the key is imported; the model
and provider stay pinned by the pilot configuration. The file is parsed as
literal assignments, never executed as shell code, and the key is not copied.

Alternatively, supply `OPENROUTER_API_KEY` in the launching shell and omit
`--env-file`. A nonempty existing environment key takes precedence. For zsh:

```zsh
read -rs 'OPENROUTER_API_KEY?OpenRouter API key: '
export OPENROUTER_API_KEY
printf '\n'
```

The following command starts paid inference. Each launch needs a new output
directory; the timestamp keeps prior results intact:

```bash
pilot_output="study-runs/magic-live-pilot-$(date +%Y%m%d-%H%M%S)"
.venv/bin/python -m study run \
  --config study/magic-pilot-config.json \
  --env-file ../AgenticAI2026_Tutorial-3/.env \
  --max-cores 4 \
  --lesson-memory \
  --problem study/problems/magic.yaml \
  --data study-data/magic-profile --output "$pilot_output"
pilot_status=$?
printf 'Pilot exit code: %s\n' "$pilot_status"
```

The pilot automatically creates `report.html`, `summary.csv`, and downloadable
PNG/SVG figures under `figures/` after search stops. The final JSON includes the
report path. On macOS, open it with `open "$pilot_output/report.html"`.
Reports are also generated for frozen failed searches; their exit status remains
nonzero. Preflight failures and interrupted commands may require fixing the error
or recovering the run before reporting.

The report opens with outcome and spending cards, followed by validation progress,
target attainment, cost/token comparisons, trial outcomes and resource-time charts.
Resource figures distinguish model-call time, local trial time and CPU queue time.
Incomplete measurements are labeled; component time summed across concurrent runs
is not suite elapsed time. HTML embeds the charts for offline viewing; PNG/SVG
downloads are separate files to keep with the report when sharing its links.
Generating reports makes no API calls and does not evaluate held-out test data.
To rebuild a report for an existing run, use:

```bash
.venv/bin/python -m study report --output "$pilot_output"
```

`--max-cores 4` sets this command's shared local training thread budget. Change
4 to your preferred ceiling; the runner caps it at the machine's logical CPU
count. Allocation is automatic, with up to four threads per fit and unused
capacity available to another independent run. Random forests use parallel
trees, histogram boosting uses OpenMP, and linear models use BLAS threads;
nested thread pools are limited to avoid multiplying these allocations.
This controls training concurrency, not OS CPU affinity or other applications.
Separate commands have separate budgets. Omit the flag (and leave `max_cores`
unset in the configuration) to retain the original single-thread baseline.

For `run`, the researcher still selects one trial at a time. For `suite`, setting
the ceiling enables up to two independent runs concurrently, overlapping their
API waits and sharing the training budget. Researcher, supervisor and reflection
calls within each run retain their required order. The USD guard remains **per
run**, so two active runs each have their own allowance. Queue waiting consumes
the run/trial time allowance but is excluded from recorded training wall time.
The trace records allocations and queue durations. The dashboard's **Host CPU**
bar measures this machine's total CPU utilization once per second, including
other applications; 100% means all logical CPUs are busy. **CPU hist** shows up
to 30 measured samples on a fixed 0–100% scale (about 30 seconds), alongside a
separately labeled `allocated` training-slot count. Allocation is not utilization:
slots can be reserved during worker startup or IO, and usually drop to zero
while awaiting API responses. The initial measurement shows `sampling`;
unavailable readings stay unknown. Host CPU is display-only data, requires no API
calls, and does not change scheduling. The `watch` display measures the machine
running the watcher, while allocation counts come from the watched trace.
Install the updated dependency lock to include `psutil` in older environments.
During a suite the
dashboard identifies the focused run, keeping its score and usage separate.
Use the same resource policy for all runs in a strategy comparison, and record
that concurrent runs compete for machine resources.

In an interactive terminal, the default CLI is a self-updating **RESEARCH LAB**
Rich dashboard in the terminal's alternate screen. Refreshes overwrite the previous
frame without first erasing every line, avoiding the blanking that can flicker in
Termius and other terminals. The normal screen and cursor return when the dashboard
stops, before final summaries are printed. A spinner marks
the current activity. The panel shows elapsed/allowed wall time (with a time
budget bar in wider terminals), trial outcomes, best validation score, targets,
cost, token usage, and whole-sentence supervisor commentary. The spinner refreshes locally
four times per second; measured findings update as events arrive. A moving spinner
means the observer is responsive, not that the model has returned new work.

**Focus** is the default. Press **`f`** without Enter to open **Details** or return
to Focus. Press **`x`** to cycle elapsed time, API cost and token chart axes;
**`[`** / **`]`** selects a run when strategies execute concurrently. The selected
run stays fixed as other strategies emit events. The border shows the shortcut when interactive keyboard input is
available. Focus keeps the active avatar, current activity, best score, targets,
experiment progress chart, complete-sentence explanation, latest lesson, time
remaining, API spend and CPU allocation. Details holds trial tables and token
breakdowns. Both views use complete
sentences for summaries and retain full content in the trace; fitting less text
never means cutting a sentence midway. Changing views makes no API calls and
does not affect the run. This also works with `study watch`. The keyboard shortcut
is available with interactive stdin on macOS/Linux and does not consume piped
input. Ctrl+C still interrupts normally and restores terminal settings.

In Details, budget bars show consumed time, attempted trials and known API spending. A separate
best-result card reports validation score, improvement and targets. The recent
experiment table distinguishes the current best, prior records, ties and failures.
The live scatterplot retains all completed scored trials and overlays the selected
best as a step line. Points use actual completion time or cumulative API accounting;
unknown accounting is labelled and omitted from cost/token coordinates. Chart
resolution is limited by terminal cells; close points may overlap.
Failures remain visible in the table and do not receive invented chart scores.
The findings card separates recorded comparisons from supervisor interpretation.
Cards stack in narrow terminals; very small windows retain activity, score, cost
and time. Enlarge the terminal to see the complete table, charts and commentary.
Rich handles resizing and cursor cleanup; `NO_COLOR` retains text labels without
color. The dependency lock includes Rich and its two additional dependencies.

`--verbose` opts into the full scrolling log: model calls and returned text,
tool arguments/results, classifier results, reviews and reflections, with a
single animated status line. This is event output, not provider token streaming.
Full detailed logs are always saved. `--no-animation` selects plain-text output,
and `--quiet` suppresses all live progress. Progress goes to stderr so the final
JSON summary on stdout remains usable. Pipes and `TERM=dumb` never receive
animation control codes.

In plain-text mode, the CLI prints a compact **FINDINGS** summary every 15 seconds
when events have changed, and immediately when a run stops. In verbose mode,
these periodic summaries accompany the logs. They report completed/unsuccessful
trials, the selected validation score, absolute improvement over the first
completed trial, targets, best observed scores by model, activity, and usage.
Supervisor commentary is labeled as model interpretation, with its trial number;
it may describe an earlier state. Summaries make no extra API calls, never enter
agent context, and run on a separate timer while model calls or local trials wait.
Use `--summary-interval 30` to reduce printed-summary frequency, or
`--summary-interval 0` to disable printed summaries. This does not disable the
interactive panel or verbose event logs.

For a run already started, attach from another terminal without restarting it:

```bash
.venv/bin/python -m study watch --output "$pilot_output" --interval 15
```

Replace `$pilot_output` with the actual run directory if the variable is not set
in that terminal. The watcher reads newly appended events once per second and
updates the same live panel. With `--no-animation` or redirected output, it prints
a snapshot immediately and changed summaries at the selected interval. It prints
the final state and exits on a stop event or a frozen summary from recovery.
`--once` prints one plain-text snapshot and exits.
It requires no key and modifies no run files; Ctrl-C stops only the watcher.
For a suite, point it at one individual directory under `runs/`. If a runner
crashes without a stop event or recovery, the watcher keeps waiting until interrupted.
The displayed last-event time is an observation, not a liveness guarantee.
The watcher reports recorded stop reasons; its exit status describes reading
the trace, not whether the underlying experiment succeeded.

Each run saves:

- `progress.log`: readable text including full returned model text and tool
  results. From another terminal, use `tail -f "$pilot_output/progress.log"`.
- `events.jsonl`: the complete structured trace, including model inputs,
  responses, tool arguments/results, generation/request identifiers, durations,
  and cumulative accounting after every model attempt.
- `checkpoint.json` and `summary.json`: selected models and final resource
  totals; `provider.json` records endpoint/pricing/runtime provenance.

The compact summaries are derived terminal views; they can be reconstructed
from `events.jsonl` with `watch --once`. The existing detailed logs are unchanged.

Cached and reasoning tokens remain separate subsets, not extra tokens added to
the input/output total. Missing billing and usage are explicitly incomplete.
Training wall time remains separate from API charges. Logs stay local; no
external telemetry service is configured. The tutorial's optional OpenTelemetry
export was an untested stub and is not required for this pilot.

Inspect `summary.json` and `events.jsonl` in that directory. A useful pilot has:

- A non-null `best` selection and several completed classifier trials.
- At least four trial attempts, a `review` after trial three, and `reflection`
  events. A run can exit zero with fewer trials, but it has not exercised the
  scheduled supervision path sufficiently.
- Complete cost accounting, charged usage, and actual served model/provider
  metadata. Confirm no persistent schema errors or repeated worker timeouts.
- A normal stop reason: `deadline`, `trial_cap`, or `dollar_cap`. If the dollar
  guard routinely binds, recalibrate before a comparison with wall time as the
  main constraint.

`run` and `suite` exit nonzero for fatal run stops (`model_failure`,
`unknown_cost`, `no_progress`, `failure`, interruption or unstarted runs), or
when no valid model was selected. Expected limits with a valid model exit zero.
Individual recoverable tool errors or failed trials remain recorded and do not
automatically invalidate an otherwise successful run.

`reference` fails nonzero on failed or timed-out fitting. `evaluate` fails
nonzero on absent selections or failed/uncertain scoring, after saving results.
`suite` still attempts evaluation and reporting after failed search runs, then
returns nonzero if search or either postrun phase failed. `completion.json`
describes postrun phases; run summaries describe search outcomes.

Keep this setup pilot validation-only: the commands above do not score the MAGIC
test partition. Run held-out evaluation only when the intended search is frozen.

After the first pilot succeeds, repeat in a fresh output directory with
`--condition periodic_reflection_literature` to exercise live scholarly retrieval.
Check for actual passages and recommendations in the trace, not just attempted
tool calls. Literature fetches follow at most five redirects, validate every
destination, and retain original/final URLs and the redirect chain. Publisher
access restrictions, PDFs, and pages requiring JavaScript can still prevent
useful retrieval; those outcomes remain visible to the supervisor.

## All five strategies

For an operational comparison, use one repeat of every strategy with the same
five-minute, 12-trial, USD 3 per-run guard. Two runs overlap and share eight local
training threads. A 20-minute deadline leaves room for three five-minute batches,
a three-minute reporting reserve and startup overhead; it is not a fixed wait.
The suite stops sooner when its runs finish. Spending guards are per run, so five
runs have five separate USD 3 guards, each checked between model calls.

```bash
.venv/bin/python -m study suite \
  --config study/magic-pilot-config.json \
  --env-file ../AgenticAI2026_Tutorial-3/.env \
  --data study-data/magic-profile \
  --output "study-runs/magic-all-strategies-$(date +%Y%m%d-%H%M%S)" \
  --repeats 1 --max-cores 8 --lesson-memory --validation-only \
  --reserve-seconds 180 \
  --deadline "$(.venv/bin/python -c 'from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat())')"
```

This exercises researcher alone, frequent supervision, periodic supervision,
periodic supervision with reflection, and periodic supervision with reflection
and literature. Each strategy has separate logs under `runs/`; the root
`report.html` compares validation results, calls, costs and timing. Held-out test
scoring is deliberately skipped. One repeat checks operation and suggests follow-up
experiments; it does not establish a reliable ranking of strategies.

## Workshop-informed decision protocol

New pilots use `structured_v1` automatically: the researcher supplies a hypothesis,
comparison baseline, expected outcome, response to advice and a concise complete
sentence for the dashboard. Validation citations are checked locally. Invalid
responses consume the existing correction/time budgets and may stop the run with
a nonzero exit; model interpretations are not treated as independently proven.

Add `--lesson-memory` to the launch command to exercise bounded lessons within that
run. Memory starts empty, keeps evidence and scope, and is a separately recorded
experimental variant. It does not import other runs or test outcomes. No separate
API request is made for UI summaries; normal response tokens and any necessary
corrections remain metered.

The output report now shows role-level time, tokens, costs and failures, advice
uptake, and equivalent-configuration warnings. Matched statistical comparisons
require multiple compatible condition runs; a single pilot cannot establish that
supervision or memory improves results.

## Retrieval and reliability checks

Literature availability does not imply retrieval occurred. Reports now separately
show offered tools, search/fetch attempts, successful results, retrieved passages,
and retrieved URLs mentioned in accepted supervisor feedback. A URL mention is
not proof that advice was useful. An enabled run with no calls is labeled
`unexercised` and cannot validate the retrieval path.

Run a credential-free check before a literature-enabled pilot:

```bash
.venv/bin/python -m study.literature_check \
  --query 'Fashion MNIST benchmarking machine learning algorithms' \
  --url https://arxiv.org/abs/1708.07747 \
  --output study-runs/literature-check.json
```

This performs one bounded search and one fetch, saves evidence, and exits nonzero
if either fails or returns no useful results/text. It makes no model calls.
The literature strategy remains optional retrieval: forcing browsing would be a
different treatment and must be recorded separately.

Current pilots use `grounded_v2`: agents cite trial IDs and metric names, while
the runner supplies exact measurements; lesson facts are generated from recorded
comparisons and explanations remain unverified interpretations. Equivalent
configurations return prior observations without another fit or trial slot.
Repeated proposals eventually stop with `no_progress`. Project and history reads
are supplied directly, avoiding redundant tool/model round trips.
