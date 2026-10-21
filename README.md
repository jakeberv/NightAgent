# NightAgent

NightAgent studies how a research apprentice adapts bounded experiments using measured results, supervision, reflection, and run-local lessons. The repository contains two applications with different execution and evaluation rules.

## Controlled experimental study

The current demo is the [five-arm Fashion-MNIST comparison](docs/five-arm-overnight.md), run with `python -m study`. It compares researcher alone, frequent supervision, periodic supervision, periodic supervision plus reflection, and periodic supervision plus reflection and lesson memory. All supervised arms use Night Science reviews; literature is disabled. The launch recipe freezes three matched repeats, 600 seconds per run, the prepared data and targets, resource sharing, and an offline acceptance audit.

The [study runner](study/README.md) uses OpenRouter and fixed scientific tools. Agents choose bounded classification/regression experiments; the harness controls splits, timeouts, artifact verification, accounting, selection and held-out evaluation. Reviews and lessons cite recorded validation measurements. A supervisor's interpretation is not ground truth. Lessons start empty in every run; transfer between independent runs is not established.

- [Current launch and acceptance criteria](docs/five-arm-overnight.md)
- [Workshop specification](SPEC.md) · [Current protocol and milestones](docs/workshop-protocol.md)
- [Named evaluation cases](docs/evaluation-cases.md) · [Demo script](DEMO.md)
- [Measured fixed classifier reference](docs/fixed-reference.md)
- [All configuration presets and their status](docs/configurations.md)
- [Targeted five-arm preflight and evidence](docs/targeted-preflight.md)
- [Problem profiles, datasets, objectives and search spaces](docs/problem-definitions.md)
- [Fashion-MNIST GPU calibration and earlier pilot recipes](docs/fashion-pilot.md)
- [Offline verification and limitations](docs/study-verification.md) · [CI dependency checks](docs/ci.md)

From the repository root, verify the workflow without model calls or data downloads:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-study.lock
.venv/bin/python -m pytest -q
.venv/bin/python -m study smoke --comparison apprentice_interactions \
  --output study-runs/offline-five-arm-smoke
```

The smoke command uses synthetic data and scripted decisions with real local classifier fits. Its results demonstrate operation, not language-model strategy performance. Neural CPU/MPS installation is separate; see [CI](docs/ci.md) and [GPU setup](docs/fashion-pilot.md).

The runner also supports the earlier five-schedule literature comparison and a three-arm supervisor-style comparison. Their settings and budgets differ from the current demo; consult the [preset index](docs/configurations.md) before launching one.

## Conversational Claude SDK prototype

The separate [conversational prototype](nightagent/README.md), launched with `nightagent/run.py`, relays meetings between a student and supervisor in separate Claude Code sessions. Plain-language protocols guide open-ended research, project files hold memory, and a private supervisor persona shapes feedback. Each invocation performs the next meeting or research phase; `--all` continues until supervisor sign-off. It does not implement the controlled study's frozen tools, equal time allowances, or held-out comparison.

```bash
python3 -m venv nightagent/.venv
nightagent/.venv/bin/pip install -r nightagent/requirements.txt
nightagent/.venv/bin/python nightagent/run.py example-projects/mnist
```

Read the [prototype setup, permissions and provider notes](nightagent/README.md) before a live run. Its [student](nightagent/STUDENT.md), [meeting](nightagent/MEETING.md), and [supervisor](nightagent/SUPERVISOR.md) protocols describe that application's behavior. The [project template](nightagent/project-template/) and [example questions](example-projects/) are starting points; generated project work is ignored by Git.

## Design history and status

The [workshop specification](SPEC.md), [current protocol](docs/workshop-protocol.md), and [shared design document](https://docs.google.com/document/d/1tBVSIyVEs3PdngYK7uHr1yEs5l3R0f5kC1OOjMMFqqA/edit?tab=t.tbzfgy1tsr0z) describe the current Fashion-MNIST study. Earlier proposals remain in [design notes](NOTES.md) and historical shared tabs. Implemented profiles also cover MAGIC, multiclass CSV, MNIST and regression.

As of 21 October 2026, MAGIC live pilots, Fashion-MNIST MPS calibration, the targeted five-arm live preflight and the fixed non-agent Fashion reference have run. The repeated five-arm overnight comparison remains pending. Passing offline checks or a short preflight does not establish strategy superiority or learning across independent runs.

The project draws on [Night Science](https://night-science.org/) principles: explore alternatives, improve questions, connect across fields, and return to measured evidence. The study makes review behavior and advice uptake observable; these are evaluation targets, not claims of scientific understanding.

## Team 5

- Josef Osumeje — josumeje@umich.edu
- Ben Moseley — b.moseley@imperial.ac.uk
- Jake Berv — jacob.berv@gmail.com
- Guido Herrera-R — guidohero@hotmail.com
- Weiwei Chen — chenww535@gmail.com
