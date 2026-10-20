# Fashion-MNIST pilot and calibration

This pilot predicts ten clothing categories from 28 × 28 grayscale images.
The primary metric is **accuracy**; macro-F1 and macro one-vs-rest ROC-AUC are
secondary checks. Accuracy targets of 0.80 and 0.85 are provisional calibration
thresholds. Measure runtime, failure rate and validation outcomes before freezing
budgets or treating either threshold as a useful attainment target. No measured
timing or performance claim is implied by these settings.

## Prepare the fixed source

Run from the NightAgent repository:

```bash
.venv/bin/python -m study.fashion_data \
  --output study-data/fashion-source/fashion-pilot.npz \
  --train-size 12000 --validation-size 3000 --seed 42

.venv/bin/python -m study prepare \
  --problem study/problems/fashion-mnist.yaml \
  --output study-data/fashion-pilot
```

The source builder downloads the four official gzip IDX files from
[the authors' repository](https://github.com/zalandoresearch/fashion-mnist).
It checks the authors' published MD5 values before parsing and records each
file's SHA-256, source URL and byte count. Cached downloads are checked again
when used. No credentials or model calls are involved.

A seeded stratified sample selects 15,000 of the 60,000 official training
examples. The profile's seeded, stratified 80/20 split then produces 12,000
training and 3,000 validation examples. The NPZ retains the selected pool's
original uint8 images and labels in `x_train`/`y_train`; `x_test`/`y_test`
contain all 10,000 official test examples, unchanged and in original order.
The official test data does not participate in sampling, fitting or calibration.
Image flattening occurs in the problem loader, after source creation.

`fashion-pilot.manifest.json` beside the NPZ records the exact selected original
training IDs, the intended train/validation IDs, and the official test IDs in a
separate namespace. It also records the selection parameters, package versions,
profile split and NPZ SHA-256. The prepared data directory has its own frozen
partition manifest and hashes. Its train/validation row IDs index the selected pool: use the
source sidecar's `selected_source_indices` to map them to official training IDs.
Prepared test row IDs start at the selected pool size (15,000); subtract that
offset to obtain the official test row index.

An identical source-builder invocation validates and reuses the frozen output.
Changed selection parameters, changed source checksum identities, incomplete
outputs or a changed NPZ checksum cause an error; nothing is silently replaced.
Choose a new output path for another sample. If changing sizes or seed, update
a copied problem profile to match the sidecar's `profile_split`, and use a new
prepared directory. Data and run artifacts remain outside version control.

## Calibrate local models before the paid search

The profile permits logistic regression, random forest, a small PyTorch MLP,
and a small PyTorch CNN. The neural models require `preprocessing: none` and
scale pixels by a fixed factor internally. Classical models may use training-only
standardization. The initial bounded ranges are:

| Model | Bounds |
| --- | --- |
| Logistic | 100–300 iterations |
| Random forest | 30–100 trees, depth 8–20, sqrt/log2 feature sampling |
| MLP | 1–5 epochs, batch 128–512, hidden width 64–128 |
| CNN | 1–5 epochs, batch 128–512, channels 8–16 |

Use the same prepared data and seed when timing representative configurations.
Record validation accuracy, secondary metrics, actual device, fitting/total wall
time and any convergence warnings or failures. Test cheap and expensive ends of
the ranges, then narrow the profile or choose trial timeouts based on those
measurements. A provisional target change creates a different frozen problem;
keep calibration and final-comparison artifacts in distinct output directories.

Install the optional pinned runtime after the study dependencies:

```bash
uv pip install --python .venv/bin/python -r requirements-study.lock -r requirements-gpu.lock
```

Repeat local calibration without any paid model calls:

```bash
.venv/bin/python -m study.calibrate \
  --configs study/fashion-calibration-configs.json \
  --data study-data/fashion-pilot \
  --output "study-runs/fashion-calibration-$(date +%Y%m%d-%H%M%S)" \
  --device mps --max-cores 4 --trial-timeout 45
```

The command checks every configuration before fitting, writes results incrementally,
and exits nonzero if any fit fails. It never evaluates the official test partition.

For the supervised paid pilot, use the dedicated configuration:

```bash
.venv/bin/python -m study run \
  --config study/fashion-pilot-config.json \
  --env-file ../AgenticAI2026_Tutorial-3/.env \
  --problem study/problems/fashion-mnist.yaml \
  --data study-data/fashion-pilot \
  --output "study-runs/fashion-pilot-$(date +%Y%m%d-%H%M%S)" \
  --device mps --max-cores 4 --lesson-memory
```

The pilot allows 300 seconds, up to 12 fits, a 45-second per-trial timeout, and a USD 3 API guard. Lesson memory is enabled. API costs include researcher, supervisor, reflection and repairs; the guard is checked after calls, so the final in-flight call can exceed it. `--device
mps` selects the neural backend on a supported Mac; logistic and random forest
remain CPU estimators. Keep the same resource policy across strategy comparisons.
Check recorded actual device and failures; do not interpret the device request
alone as proof that a GPU fit succeeded. Keep this pilot validation-only, and
evaluate the official test set only after the intended search is frozen.


## Comparing interaction strategies

The primary scientific question is which **interaction strategy** reaches a fixed
accuracy using the least API cost/tokens, not merely which classifier has the
highest score. Reports now show per-target reached/not-reached counts, first
attainment cost, input-plus-output tokens and elapsed time, plus attainment curves
whose denominator includes every scheduled run. Cached/reasoning tokens are
subsets and are not added twice. Unknown accounting remains unknown.

Means among successful runs are explicitly conditional. A run that misses a target
is observed only up to its final budget; no hypothetical convergence cost is
estimated. Use the reach fraction together with conditional cost, and compare final
accuracy as well. One repeat per strategy tests plumbing; it cannot establish a
reliable efficiency winner. Freeze targets and budgets before the repeated study.
Keep hardware policy, model/provider, memory setting and data identical across
strategies. Wall time includes API latency and waiting for shared compute; USD
tracks API spending, not local electricity or hardware depreciation.

To test **all five strategies** with one repeat each and generate the comparison
report without touching test labels:

```bash
.venv/bin/python -m study suite \
  --config study/fashion-pilot-config.json \
  --env-file ../AgenticAI2026_Tutorial-3/.env \
  --problem study/problems/fashion-mnist.yaml \
  --data study-data/fashion-pilot \
  --output "study-runs/fashion-all-strategies-$(date +%Y%m%d-%H%M%S)" \
  --repeats 1 --validation-only --reserve-seconds 120 \
  --deadline "$(.venv/bin/python -c 'from datetime import datetime,timedelta; print((datetime.now().astimezone()+timedelta(minutes=20)).isoformat())')"
```

Two strategy runs can overlap their API calls. They share a four-core local
ceiling and serialize neural fits on the GPU; GPU waiters hold no CPU allocation.
Five 5-minute allowances need at most three search waves (15 minutes), plus setup
and report time. The five per-run USD 3 guards total USD 15 before possible final
call overruns. Use the single-run command above for the shortest check. Interactive
terminals show the self-updating dashboard by default; `--verbose` enables full
streaming logs. Both commands retain full event logs and create an HTML report.


## Local calibration observed on 20 October 2026

On this M1 Max, macOS arm64/Python 3.12/PyTorch 2.14.1, the final six-fit
calibration used four CPU threads and MPS for neural training. All six completed
in 21.78 seconds, with no API calls and no test-set scoring.

| Configuration | Validation accuracy | Complete trial wall time |
| --- | ---: | ---: |
| Logistic, C=1, 100 iterations, standardized | 0.8217 | 2.05 s |
| Random forest, 100 trees, depth 20, sqrt features | 0.8560 | 3.42 s |
| MLP, width 64, 1 epoch, batch 128 | 0.7650 | 3.12 s |
| MLP, width 128, 5 epochs, batch 128 | 0.8387 | 3.98 s |
| CNN, 8 channels, 1 epoch, batch 128 | 0.7393 | 3.57 s |
| CNN, 16 channels, 5 epochs, batch 128 | 0.8547 | 5.63 s |

All neural records confirm `device: mps`; saved artifacts use CPU inference.
These are one-seed calibration observations, not independent estimates of test
accuracy or evidence that one interaction strategy wins. The 0.80 target is a
basic attainment check and 0.85 is already reachable by a default-like forest.
Reassess target difficulty after the pilot, then freeze targets before overnight
comparisons. Runtime varies with machine load, warm-up and chosen parameters.
Machine-local evidence: `study-runs/fashion-calibration-final-20261020/calibration.json`.
