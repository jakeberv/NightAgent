# 002 — Logistic regression baseline

**Question.** How well does a linear softmax (multinomial logistic regression) classifier do on MNIST, how stable is it across seeds, and *what* does it get wrong compared with the nearest-class-mean template from 001? (Action 3, M00.)

**Approaches considered.** (i) scikit-learn `LogisticRegression` (L-BFGS, exact convex optimum) — extra dependency, and doesn't exercise the shared training tool; (ii) PyTorch `Linear(784,10)` + cross-entropy trained with Adam via `tools/train.py` — same tool every later model will use, so comparisons are like-for-like. Chose (ii). Not tuned: no regularisation, Adam lr 1e-3, batch 128, 20 epochs, CPU (pilot: 0.18 s/epoch; MPS was 13× slower for this tiny model). Seed varies the init and batch order; the data split is fixed.

**Prediction (written before running).**
- Val ≈ 92.3 %, test ≈ 92.5 % (literature: softmax regression on MNIST ≈ 92–93 %; LeCun et al. 1998 report 12.0 % error for a linear classifier trained differently).
- Seed std < 0.15 pp — the problem is convex, so seeds only change the optimisation path.
- Train accuracy ≈ 93.5 %: small train–val gap (the model underfits, not overfits).
- Top confusions: 4↔9, 3↔5, 2↔8, 7↔9, 5↔8. The "thin digit → 1" errors of the template will mostly vanish.
- Test − val within ±0.5 pp despite the small shift found in 001.

**Reproduce.** From the project root:
```bash
.venv/bin/python experiments/002-logreg-baseline/run.py
```

## Results
Runtime: 12 s total (3.3 s training per seed, CPU). All numbers: `results/metrics.json`.

| Metric (3 seeds) | mean ± std |
|---|---|
| Train acc | 93.39 ± 0.03 % |
| **Val acc** | **91.86 ± 0.34 %** (91.54 / 91.82 / 92.22) |
| **Test acc** | **92.43 ± 0.06 %** (92.49 / 92.37 / 92.44) |
| Params | 7,850 |
| Nearest class mean (001), test | 81.98 % |

Figures: `results/confusion_test.png`, `results/confusion_val.png`, `results/per_class_vs_ncm.png`, `results/learning_curves.png`, `results/weights_vs_means.png`, `results/confident_errors.png`.

**Errors (test, pooled over 3 seeds).** Top: 2→8 (119), 4→9 (114), 5→3 (108), 8→5 (94), 5→8 (89), 7→9 (81), 9→7 (80). Weakest classes: 5 (87.3 %), 8 (87.6 %), 2 (88.7 %); strongest 1 (97.9 %), 0 (97.8 %). Errors *into* "1" fall from 331 (template) to 42 per seed.

**Learning dynamics.** Val accuracy plateaus by ~epoch 5 and then fluctuates ±0.2–0.3 pp epoch-to-epoch (constant-lr Adam, no decay). The val seed spread (0.34 pp) is therefore mostly *which epoch you happen to stop on*, not different solutions; test spread is smaller (0.06 pp) partly because test is 2× larger.

**What the weights look like.** The learned weight images are *not* clean digit templates (correlation with centred class means only 0.32–0.43). Their colour scale is dominated by large weights on the **outer ring of rarely-inked pixels**: with no regularisation, a pixel that is non-zero in only a few training images can take an arbitrarily large weight to fix those few images. The digit-shaped structure is visible only faintly in the interior.

## Comparison with prediction
- Test ≈ 92.5 %: ✅ 92.43 %. Val ≈ 92.3 %: ⚠️ lower, 91.86 %.
- Seed std < 0.15 pp: ✅ on test (0.06); ❌ on val (0.34) — I ignored last-epoch fluctuation of un-decayed Adam.
- Train ≈ 93.5 %, small gap: ✅ 93.39 %, gap 1.5 pp to val → underfitting regime.
- Top confusions: ✅ 4↔9, 3↔5, 2↔8, 7↔9, 5↔8 all in the top 10; "→1" errors vanish (331 → 42): ✅.
- Test − val within ±0.5 pp: ❌ +0.57 pp, and in the *opposite* direction from what the 001 shift might suggest (test is easier, not harder). With 5k val images the sampling SE is ≈ 0.38 pp, so a 0.57 pp gap is ~1.5 SE: not conclusive evidence of a real val/test difficulty difference.

## Conclusion
- Baseline: **logistic regression = 92.43 ± 0.06 % test** (val 91.86 ± 0.34 %), in 3 s on a laptop CPU. The bar for "best" is at least this; the literature ceiling is ~99.8 %, so ~7 pp of headroom lies between linear and state of the art.
- Learning a linear discriminant instead of averaging templates gains +10.5 pp. It fixes the ink-vs-shape confusion (errors into "1" drop ~8×) and helps most on the most variable classes (5: 69 → 87 %, 8: 74 → 88 %, 2: 75 → 89 %).
- What it can't fix: the 4/9, 7/9, 3/5/8 and 2/8 confusions identified in pixel space in 001. These need features that are not linear in pixels (e.g. stroke topology: a closed top loop on 9 vs open 4; position-invariance).
- The model is in the *underfitting* regime (train 93.4 %), so more capacity, not more regularisation, is what should move test accuracy. But regularisation (weight decay) would likely make the weights interpretable and may slightly help — cheap to check.
- Methodological notes for future experiments: (a) val accuracy from a single final epoch carries ±0.3 pp noise → use lr decay or average the last few epochs; (b) differences < ~0.4 pp on val (5k) are within sampling noise and need test or multiple seeds to resolve.
