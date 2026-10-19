# M01 brief — week 1 (2026-10-19)

Total compute this week: about 35 s, under the 10-minute demo cap.

## 1. Agreed actions → status
1. **Explore MNIST: done.** See [001](../experiments/001-data-exploration/README.md). Covers samples, class balance, mean/std images, class similarity, PCA, and train/val/test shift.
2. **Reusable tools: done.** `tools/data.py` (fixed-seed 55k/5k/10k split, checksummed), `tools/train.py` (logs val and test accuracy, time and parameter count), `tools/plotting.py`.
3. **Logistic regression baseline: done.** See [002](../experiments/002-logreg-baseline/README.md): 3 seeds, confusion matrices, plus weight visualisation (a small extra, labelled as initiative in ACTIONS.md).

## 2. Key results
- **Logistic regression reaches 92.43 ± 0.06 % on test** and 91.86 ± 0.34 % on val, with 7,850 parameters and 3 s of training per seed. [002](../experiments/002-logreg-baseline/results/confusion_test.png)
- **A single average image per class reaches 82.0 % on test.** Its errors match ink rather than shape: thin digits get called "1", with 331 such errors versus 42 for logistic regression. [002](../experiments/002-logreg-baseline/results/per_class_vs_ncm.png)
- **The hard pairs exist before any learning.** The closest class means are 4–9, 7–9, 3–5, 5–8 and 3–8, and these are the same pairs logistic regression still gets wrong (2→8 119, 4→9 114, 5→3 108, pooled over 3 seeds). [001](../experiments/001-data-exploration/results/class_mean_distance.png)
- **The test set is slightly shifted from train** (+1.4 % ink, KS 0.023 > 0.015), most for 6 and 9. Train and val are indistinguishable. [001](../experiments/001-data-exploration/results/split_shift.png)

## 3. Surprises and failures
- Test accuracy came out higher than val (+0.57 pp), although I expected the shift to make test harder. The gap is about 1.5× the val sampling SE, so it is inconclusive.
- Val seed spread was 0.34 pp against the predicted < 0.15. The cause is epoch-to-epoch fluctuation from constant-lr Adam, not different solutions.
- The learned weights are not clean templates. Without regularisation, large weights sit on rarely-inked border pixels.

## 4. What I think it means (interpretation)
Linear models are in an underfitting regime with a ceiling of about 92.5 %. The remaining ~7 pp to state of the art should come from features that are non-linear in pixels: stroke topology (a closed loop on 9 versus an open 4) and tolerance to shifts and slant. If that is right, the gain from adding capacity should be concentrated on the hard pairs.

## 5. Proposed next steps
- **A. Capacity ladder** (recommended): MLP → small CNN → CNN + augmentation, each ≤ 3 min. Track per-pair error reduction to explain *why* each rung helps. About 4 experiments, ~10 min of compute.
- **B. Logistic regression + weight decay / lr decay**: cleaner weights and a less noisy val estimate. 1 experiment, < 1 min.
- **C. Resolve the test shift**: per-image slant and thickness from image moments. 1 experiment, < 1 min.
- **D. Classical non-neural comparators**: k-NN and an RBF SVM on PCA features. They bring a different inductive bias, which helps the "why" question. About 2 experiments; the SVM may need subsampling to stay under 3 min.

## 6. Questions for you
1. Should next week follow A, possibly plus B and C as cheap add-ons, or would you rather have D for diversity?
2. To make val estimates less noisy, may I use lr decay or average the last epochs as a standard training choice from now on?
3. No pending.md items.
