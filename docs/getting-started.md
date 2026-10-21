# Try NightAgent locally

Run a small study and open its report before setting up a model account. This
demonstration uses scripted agent decisions and real CPU classifier fits on
synthetic data. Running it needs no API key, paid model calls, literature access,
or dataset downloads.

## Install the study environment

Start in the `NightAgent` repository directory with Python 3.12 installed:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-study.lock
```

The [base lock](../requirements-study.lock) pins the study dependencies and was
verified on macOS arm64. This first demonstration needs neither PyTorch nor an
Apple GPU. The separate [Linux CPU environment](ci.md#local-reproduction-and-lock-updates)
includes the neural dependencies used by developer checks. Optional Apple MPS
installation and calibration are in the [Fashion-MNIST guide](fashion-pilot.md).

## Run the five-arm demonstration

Use a new output directory for every attempt. The timestamp below gives this
demonstration its own folder:

```bash
demo_output="study-runs/local-demo-$(date +%Y%m%d-%H%M%S)"
.venv/bin/python -m study smoke \
  --comparison apprentice_interactions --output "$demo_output"
```

An interactive terminal shows the active role, completed experiments, best
validation score and remaining budget. Press `f` for Details, `l` for the live
log, and `x` to change the chart axis. Add `--verbose` for the scrolling event
log or `--quiet` to save results without the live display. Full logs are saved
in every mode. More controls are in the [operator reference](study-reference.md#live-display-and-logs).

The five arms are:

| Arm | What changes | Lesson memory |
| --- | --- | --- |
| `researcher_alone` | Researcher plans experiments independently | On |
| `frequent` | Supervisor reviews after each attempt | On |
| `periodic` | Supervisor reviews after every three attempts | On |
| `periodic_reflection` | Periodic supervision plus explicit researcher reflection | On |
| `periodic_reflection_no_memory` | Same supervision and reflection as the preceding arm | Off |

All supervised arms use Night Science and an initial framing step. Literature is
disabled. Lesson memory starts empty for each independent run and never transfers
between repeats. It is on by default elsewhere in the runner. `--no-lesson-memory`
opts out for a single `run` or an earlier comparison mode; flags do not change
this suite's fixed mapping. See the [memory contract](memory-default.md).

This small fixture checks that experiments, interactions, memory and reporting
work together. Its scripted decisions cannot establish that supervision,
reflection or memory improves a model's research strategy. It is also shorter
than the interaction coverage required by the overnight acceptance audit.

## Open the report

The command prints the path to `report.html`. On macOS, open it with:

```bash
open "$demo_output/report.html"
```

On Linux, use `xdg-open "$demo_output/report.html"`, or open the file directly
from your browser. The HTML embeds its charts and can be viewed locally. Look
at validation progress, target attainment, trial outcomes, and the recorded
supervisor/reflection traces. Model accounting belongs to the scripted fixture;
it is not a live API price estimate.

The output also contains `summary.csv`, per-arm evidence under `runs/`, and
downloadable graphics under `figures/`. Keep the `figures/` folder with the report
if you want its PNG/SVG download links to work. To rebuild the report from saved
evidence without model calls:

```bash
.venv/bin/python -m study report --output "$demo_output"
```

## Continue when ready

For a real Fashion-MNIST comparison, follow the
[five-arm runbook](five-arm-overnight.md). That is a separate, paid workflow:
prepare its data, configure credentials, verify account funding and spending
guards, and run a new bounded pilot before the overnight launch. Earlier paid
results used a different memory policy and do not validate the current protocol
or its cost estimate.

To use your own local dataset, start with the
[problem-definition guide](problem-definitions.md). For presets and command
details, use the [configuration index](configurations.md) and
[operator reference](study-reference.md). Developer tests are optional for this
first experience; their supported environments and commands are in
[continuous integration](ci.md), with named checks in
[engineering evaluation cases](evaluation-cases.md).

The separate [conversational Claude SDK prototype](../nightagent/README.md) has
its own installation and workflow. It is not needed for this study demonstration.
