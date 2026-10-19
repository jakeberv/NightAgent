# 001 — Data exploration

**Question.** What does MNIST look like, how do the classes differ from each other, and do the train / val / test splits come from the same distribution? (Action 1, M00.)

**Approaches considered.** (i) Pure visual inspection (sample grids); (ii) per-class summary statistics (mean/std images, ink, within-class spread); (iii) geometric class similarity (distance between class means, nearest-class-mean classifier as a "how far does a template get you" probe — borrowed from classical template matching / prototype methods); (iv) linear structure via PCA; (v) split-shift tests (pixel histograms, ink distributions, two-sample KS statistic — standard covariate-shift diagnostics). All are cheap, so all are done. t-SNE/UMAP were skipped: extra dependency and runtime, little extra insight for week 1.

**Prediction (written before running).**
- Classes roughly balanced: each 9–11 %; "1" most frequent, "5" least.
- Most similar class-mean pairs: 4–9, 7–9, 3–5, 3–8, 5–8.
- Nearest-class-mean classifier: ~80–82 % val accuracy.
- "1" has the least ink and smallest within-class spread; "0"/"8" the most ink.
- Train vs val: indistinguishable (random split). Test: small but measurable differences (disjoint writers), KS statistic on ink < 0.05.
- PCA: ~85–90 components for 90 % variance; first 2 PCs separate 0 and 1 but overlap most others.

**Reproduce.** From the project root:
```bash
.venv/bin/python experiments/001-data-exploration/explore.py
```

## Results
Runtime: 4 s compute (19 s wall incl. one-off matplotlib font cache). All numbers: `results/metrics.json`.

| Figure | Shows |
|---|---|
| `results/samples.png` | 10 random training digits per class |
| `results/class_balance.png` | class % per split |
| `results/class_mean_std.png` | per-class mean and pixel-std images |
| `results/class_mean_distance.png` | L2 distance between class means |
| `results/ncm_confusion_val.png` | nearest-class-mean errors on val |
| `results/pca.png`, `results/pca_components.png` | PCA spectrum, PC1–PC2 scatter, top components |
| `results/split_shift.png` | train vs test mean image, difference, ink histograms |

**Classes.** Balanced within 9–11.3 %: "1" most frequent (11.3 % train), "5" least (9.0 %). Val (random 5k) deviates by up to ±0.7 pp from train purely by sampling.

**Class differences.**
- Ink: "1" has by far the least (59.6, ≈ half the mean of 102), "0" the most (135.7), then 8 (117.9) and 2 (117.0).
- Within-class spread (mean L2 to class mean): "1" tightest (4.6); 2 (7.1) and 0 (7.0) most variable. The std images show *where* variation lives: "1" varies mainly in slant (the bow-tie std pattern), 0 in size/aspect, 7 and 9 in the stem.
- Closest class-mean pairs: 4–9 (2.49), 7–9 (2.98), 3–5 (3.11), 5–8 (3.11), 3–8 (3.63), 5–9 (3.78).
- Nearest-class-mean classifier (one template per class, no learning beyond averaging): **80.0 % val, 82.0 % test**. Top val errors: 4→9 (55), 5→3 (54), 9→4 (53), 8→3 (51), 3→8 (37) — the close-mean pairs — plus an unpredicted group *into* "1": 5→1 (44), 7→1 (31), 8→1 (30). Interpretation: under L2 distance the faint, low-ink "1" template is the closest match for any thin or lightly-inked digit, i.e. the template method confuses *ink amount* with *shape*. A single template also cannot represent within-class variation such as slant.

**Linear structure.** 11 PCs explain 50 % of variance, 44 → 80 %, **87 → 90 %**, 154 → 95 %, 331 → 99 %. PC1–PC2 separate "0" and "1" at opposite ends; other classes overlap heavily in 2D.

**Split shift.**
- Train vs val: indistinguishable (ink KS = 0.0066 < critical 0.020), as expected for a random split.
- Train vs test: small but **statistically significant** shift — test digits carry 1.4 % more ink (103.9 vs 102.4; KS = 0.023 > critical 0.015). The test−train mean image shows a structured (diagonal stroke-like) difference of up to ~0.03 intensity, not noise. Per class the shift is largest for 6 (KS 0.082), 9 (0.065), 8 (0.055), 0 (0.051) — above the per-class critical value (~0.047) — so it is not only a class-mix effect. Consistent with MNIST's test set using writers disjoint from training.

## Comparison with prediction
- Balance, which classes are extreme, ink ordering, "1" tightest: ✅ as predicted.
- Closest pairs: ✅ exactly the five predicted pairs are the top five (order differs).
- Nearest-class-mean ≈ 80–82 %: ✅ (80.0 val / 82.0 test).
- PCA ~85–90 components for 90 %: ✅ (87).
- Test shift: ⚠️ predicted "small, KS < 0.05" — overall KS 0.023 is small, but I did not predict it would be *significant*, nor the per-class KS reaching 0.08 for "6".

## Conclusion
- MNIST is balanced and train/val are exchangeable, so val accuracy should be an unbiased estimate of *train-distribution* accuracy.
- The test set is slightly shifted (different writers, a bit more ink). Expect test accuracy to differ from val by a small, possibly systematic amount; val-to-test gaps should not be read as overfitting without checking this.
- The hard class pairs (4/9, 7/9, 3/5/8) are already visible in pixel space before any model is trained. Prediction for later models: these pairs will dominate errors for linear models and shrink most for models that handle spatial variation (CNNs, augmentation).
- Intra-class variation (slant, thickness, size) is the main thing a single template misses; a learned linear model can only partly fix this.

**Open / not done.** Whether the test−train mean-image difference is a slant or a thickness effect was not resolved (needs per-image slant/thickness estimates, e.g. image moments — ~1 min). Class-reweighted comparison not done.
