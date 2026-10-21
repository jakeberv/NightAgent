# Named workshop engineering evaluation

Run the eight named acceptance cases from the `NightAgent` directory:

```bash
.venv/bin/python -m study.workshop_eval --output study-runs/workshop-evaluation
```

This command makes no model, provider, literature, or dataset-download requests.
It runs existing pytest checks with synthetic data, scripted decisions, controlled
clocks, and local workers. Some checks train real bounded CPU classifiers; the
audit checks use an explicitly scripted five-arm fixture.

These are **engineering acceptance cases**, not scientific observations. The
scientific comparison has **15 runs: one dataset × five arms × three repeats**.
Passing the acceptance cases establishes the checked implementation behaviors;
it does not establish which arm is more effective. Pytest parameter counts and
the number of acceptance cases are separate from the scientific run count.

The machine-readable mapping is
[`study/evaluation_cases.json`](../study/evaluation_cases.json). Each entry names
its check and lists the exact existing pytest function node IDs. A function node
includes all its parametrized children.

| Case ID | Required behavior |
| --- | --- |
| `artifact-data-isolation` | Reproducible, disjoint splits; a verified real artifact produced without test data; worker input and environment isolation. |
| `proposal-repair-and-citations` | Invalid evidence repaired within the existing budget before training; model-supplied measurements rejected; recorded validation citations attached to accepted contracts. |
| `feedback-schedule` | Expected review/reflection cadence, including failed trials, continued search after target attainment, and no terminal review. |
| `memory-isolation-and-history` | Run-local lessons survive history truncation and recovery; older evidence remains available across roles. |
| `budget-and-deadline` | Cost/trial limits and insufficient remaining time prevent additional work. |
| `late-results-and-selection` | Results recorded before selection; failed, timed-out, late and nonfinite results excluded; earliest ties and named target crossings retained. |
| `heldout-separation` | Held-out data hidden from agent context; frozen selections scored once; interrupted scoring reservations retained as uncertain. |
| `audit-integrity` | Complete evidence passes without mutation; missing, inconsistent, corrupt or tampered evidence and artifacts fail independent checks. |

To run a subset, repeat `--case`. The whole subprocess has a configurable
300-second timeout:

```bash
.venv/bin/python -m study.workshop_eval \
  --output study-runs/workshop-evaluation-subset \
  --case budget-and-deadline --case audit-integrity --timeout 120
```

The runner invokes `sys.executable -m pytest` once for the union of selected
tests. Shared tests execute once. A small pytest collection hook in the runner
saves node IDs before deselection; this lets a case fail when one parametrized
child is missing even if its siblings pass. Inherited `PYTEST_ADDOPTS` is removed
so shell preferences cannot silently change the requested execution. Repository
pytest settings still apply, and any resulting missing required nodes fail.

The output directory contains:

- `results.json`: overall verdict, one verdict per named case, individual node
  outcomes, missing nodes, execution errors, command, timing, and artifact paths.
- `junit.xml`: raw pytest results, using xunit1 to retain source paths.
- `collected-nodes.json`: node IDs discovered by that same pytest invocation.
- `pytest.stdout.log` and `pytest.stderr.log`: complete subprocess output.

A case passes only when every mapped function is collected and every collected
required parameter has a passing JUnit result. A missing, skipped, failed or
errored check fails its named case. A nonzero pytest exit, timeout, or missing or
invalid JUnit/collection evidence also fails the overall evaluation. On timeout,
the process group is killed on POSIX systems and the receipt/logs are retained;
pytest may not have finished writing JUnit or collection evidence.

Exit status is `0` for a passing evaluation, `1` for failed checks or execution,
and `2` for invalid arguments or an unusable output location. Existing evaluation
artifacts are never reused or overwritten: choose a fresh output path for a new
receipt. A subset receipt identifies only its selected cases and does not imply
that the full package passed.

Runner regression tests are in
[`tests/test_workshop_eval.py`](../tests/test_workshop_eval.py); they exercise real
local pytest subprocesses, including partial parameter deselection, skips,
assertion failures, fixture errors, nonzero exits, and timeout receipts.
