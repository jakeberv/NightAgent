# Administrator evaluation

From the NightAgent repository root:

```sh
./admin_demo/run.sh
```

This runs **eight offline engineering cases**, a **fixed logistic-regression
reference**, and **one real researcher with memory for seven experiments** on
Fashion-MNIST. It then checks the evidence and prints the location of a short
`report.html`. Open that file in your browser.

Allow roughly 2–5 minutes after setup; hardware and API latency affect timing.
The researcher has a 300-second search allowance, 45 seconds per fit, and a
$1 API spending guard. An in-flight call can exceed the guard. The first run
downloads and prepares the public dataset if it is not already present.
Baseline, engineering checks, preparation and reporting are outside the search
allowance. The official test set is never scored.

## One-time setup

Use Python 3.12. From the repository root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-study.lock -r requirements-gpu.lock
```

Set `OPENROUTER_API_KEY` in your environment, or put
`OPENROUTER_API_KEY=your-key` in **admin_demo/.env** (ignored by Git).
You can instead pass `--env-file /path/to/credentials.env`. Check that the key
has at least $1 available before running. No key is included in this package.
The default uses Apple MPS when available, otherwise CPU; `--device cpu` forces
CPU. The pinned neural environment was verified on macOS arm64; other machines
may need the repository's [Linux CPU environment](../docs/ci.md).

## Saved fallback — no setup, key or dataset

```sh
./admin_demo/run.sh --replay
```

Or open [saved/report.html](saved/report.html) directly. Replay needs only
Python 3 when run from the command line. It is explicitly labeled **SAVED
REPLAY**: it displays a recorded real run and its original verdict, without
rerunning tests, calling a model or checking the original model artifacts.
The bundled 21 October 2026 recording passed: seven fits in 101 seconds,
$0.176544 API cost, one lesson update and five later contexts receiving it.

## What to inspect

1. **Agent loop:** each decision, `run_analysis` arguments, measured result,
   and the evidence cited by the next decision. Hypotheses are model
   interpretations; measurements come from the training tool.
2. **Memory:** an evidence-linked lesson is saved and delivered to a later
   researcher context. This is context memory, not model-weight training or
   proof of a memory benefit.
3. **Evaluation:** eight named pass/fail cases, one research repeat, validation
   accuracy versus the fixed reference, runtime, model calls, tokens and cost.
   Seven experiments are steps within one run, not seven independent cases.

Passing requires all eight engineering cases, seven completed fits, verified
artifacts, grounded citations, a valid reference, later lesson delivery, complete
accounting and the expected stopping rule. Beating the reference is **not** a
pass requirement; the reference and agent use unequal effort. This demonstrates
Tutorial 1's tool loop/traces and Tutorial 2's memory, without a supervision or
strategy-superiority claim.

## Files and outputs

- `run.sh` / `run.py`: entry point and short HTML report; `config.json`: fixed limits.
- `evidence.py`: reuses the study's audit and checks the solo trace.
- `saved/`: portable real-run evidence and its readable report.
- `output/<timestamp>/`: fresh report, JSON verdict, console log, engineering
  receipts, baseline, full agent journal and trained artifacts (ignored by Git).

The directory contains the complete admin workflow and fallback. Live execution
reuses `../study/` and the repository's dependencies; it is not a second copy of
the research engine. Replay works with this directory alone. Use `--output DIR`
to choose a **new** output directory. Exit code 0 means pass (recorded pass for
replay); 1 means failure. Failed live attempts retain logs and never silently
switch to replay.

To check this wrapper without paid calls: `.venv/bin/python -m pytest admin_demo/test_admin.py -q`.
