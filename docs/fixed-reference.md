# Measured fixed reference

The predeclared Fashion-MNIST reference is standard-scaled logistic regression,
`C=1`, `max_iter=300`, training seed 42, with one CPU core and a 120-second
timeout. It uses the same frozen 12,000/3,000 training/validation partitions as
the five-arm experiment. It makes no model calls and does not score held-out data.

On 21 October 2026 it completed in **4.74 seconds**:

| Validation metric | Value |
| --- | ---: |
| Accuracy (primary) | 81.03% |
| Macro-F1 | 0.80904 |
| Macro one-vs-rest ROC-AUC | 0.97336 |

The [portable receipt](evidence/fashion-fixed-reference.json) records the declared
configuration, frozen data/problem identities, software version, actual estimator,
metrics and verified artifact SHA-256. Full local evidence is under
`study-runs/fashion-fixed-reference-20261021-000433/`; model binaries are ignored
by Git. The first invocation stopped before fitting because its output directory
already held the declaration. The successful fit used a fresh `trial/` child;
there was no reference tuning or selection among fits.

To reproduce, choose a new output path that does not exist:

```bash
.venv/bin/python -m study reference \
  --data study-data/fashion-mnist --problem study/problems/fashion-mnist.yaml \
  --output study-runs/fashion-reference-reproduction --seed 42 --timeout 120
```

The real seven-attempt preflight's adaptive arms reached 85.40–87.50% validation
accuracy. That comparison shows task headroom beyond this fixed classifier;
different search effort prevents attributing the difference solely to agency.
The fixed classifier is outside the five treatments. Researcher alone remains
the matched adaptive baseline. Neither this fit nor the preflight establishes a
general advantage of supervision, reflection or memory.
