# NightAgent

**An AI research apprentice that experiments, receives feedback, and keeps evidence-linked lessons.**

NightAgent explores how an apprentice can become a better research partner. A human sets the question and limits; the apprentice chooses experiments, measures results, and decides what to try next. A supervisor can challenge its reasoning and suggest alternatives. Inspired by [Night Science](https://night-science.org/), the aim is to make exploration and changes of direction visible and testable.

## What you can see

Our workshop demonstration asks the apprentice to compare classifiers for **Fashion-MNIST**, a dataset of clothing images. You can follow a recommendation through the next experiment, its measured outcome, and the lesson retained for later decisions. A comparison report brings together accuracy, time, cost, and the interaction record.

The study compares five ways of working:

| Approach | What changes |
|---|---|
| Researcher alone | Works without supervisor feedback |
| Frequent supervision | Receives feedback after each experiment |
| Periodic supervision | Receives feedback after every three experiments |
| Periodic supervision and reflection | Also reflects after each experiment |
| The same approach without lesson memory | Tests the contribution of retaining lessons |

The protocol enables lesson memory in the first four approaches. Every independent run starts fresh. Data, available experiments, and time allowances stay fixed so we can inspect the value and cost of these interactions. Retained lessons are context memory; the language model's weights do not change.

## Start here

- **Administrator evaluation:** [one-command solo demo](admin_demo/README.md), with seven live experiments, memory, a short report and a saved replay fallback.
- **Watch the demo:** [presentation walkthrough](DEMO.md) and [saved real interaction replay](docs/evidence/fashion-demo/demo.md).
- **Try it locally:** [getting started](docs/getting-started.md) provides an offline example with no API key or data download.
- **Understand the project:** [goals and scope](docs/project-goals.md), [one-page workshop spec](SPEC.md), and [milestone checklist](docs/workshop-milestones.md).
- **Run or develop the study:** use the [documentation guide](docs/README.md) for setup, experiment methods, configuration, and launch instructions.

## Run the complete comparison

From this repository, install the [study environment](docs/getting-started.md#install-the-study-environment)
and configure [OpenRouter credentials](docs/magic-pilot.md). Both commands below
make paid model calls: five approaches × three repeats, ten minutes per run,
with a $5 guard per run ($75 combined; an in-flight call can exceed a guard).
They finish with held-out evaluation, a comparison report and an acceptance audit.
Check funding and run the [operational preflight](docs/workshop-readiness.md#what-requires-new-validation)
before another full comparison. The previous Fashion run cost at least $22.44;
remeasure costs under the corrected context before projecting another run.

**Fashion-MNIST, matching the overnight design.** First [prepare the data and
install the neural dependencies](docs/fashion-pilot.md). This uses Apple MPS;
keep the Mac awake and connected to power. The [overnight runbook](docs/five-arm-overnight.md)
also provides a sleep-preventing launcher with a retained console log.

```bash
run_output="study-runs/fashion-five-arm-$(date +%Y%m%d-%H%M%S)"
deadline="$(.venv/bin/python -c 'from datetime import datetime,timedelta; print((datetime.now().astimezone()+timedelta(hours=2)).isoformat())')"
.venv/bin/python -m study suite \
  --config study/fashion-five-arm-overnight-config.json \
  --env-file ../AgenticAI2026_Tutorial-3/.env \
  --problem study/problems/fashion-mnist.yaml --data study-data/fashion-mnist \
  --repeats 3 --order-seed 2026 --reserve-seconds 1200 \
  --deadline "$deadline" --audit --output "$run_output"
```

**MAGIC Gamma Telescope, CPU only.** The earlier astronomy task compares gamma
and hadron events using logistic regression, random forests and gradient
boosting. It needs no GPU or PyTorch. Save the [UCI source](https://archive.ics.uci.edu/dataset/159/magic+gamma+telescope)
as `study-data/magic-source/magic04.data`, then run:

```bash
.venv/bin/python -m study prepare \
  --problem study/problems/magic.yaml --output study-data/magic-five-arm
run_output="study-runs/magic-five-arm-$(date +%Y%m%d-%H%M%S)"
deadline="$(.venv/bin/python -c 'from datetime import datetime,timedelta; print((datetime.now().astimezone()+timedelta(hours=2)).isoformat())')"
.venv/bin/python -m study suite \
  --config study/fashion-five-arm-overnight-config.json --device cpu \
  --env-file ../AgenticAI2026_Tutorial-3/.env \
  --problem study/problems/magic.yaml --data study-data/magic-five-arm \
  --repeats 3 --order-seed 2026 --reserve-seconds 1200 \
  --deadline "$deadline" --audit --output "$run_output"
```

The astronomy command reuses the same interaction and budget settings; its
problem profile supplies the CPU classifiers and ROC-AUC targets instead of the
Fashion models and accuracy targets. See the [MAGIC guide](docs/magic-pilot.md)
for the CPU verification and a shorter pilot. If `OPENROUTER_API_KEY` is already
set, omit `--env-file`; otherwise change that path to your credential file.
Open `$run_output/report.html` after either run, and inspect `audit-summary.json`
before treating its comparison as accepted.

## Where we are

The [overnight comparison](docs/overnight-results.md) ran all 15 attempts and
produced 349 verified fits, with $22.444005 known cost and two calls with unknown
billing.
Its original audit failed: two arms stopped early and one final supervisor note
could not be repaired before the deadline. The saved results establish no winning
approach or memory benefit. All 12 memory-enabled runs saved and later delivered
lessons, so the [demo](DEMO.md) can show the mechanism with those limits visible.
See [readiness](docs/workshop-readiness.md) for the reliability correction and
what a new accepted comparison would require.

This repository also contains a separate [conversational research prototype](nightagent/README.md) built with the Claude Agent SDK. It supports open-ended student–supervisor meetings and project files; the controlled workshop study described above provides the fixed experiments and comparative evaluation.

## Team 5

Josef Osumeje · Ben Moseley · Jake Berv · Guido Herrera-R · Weiwei Chen
