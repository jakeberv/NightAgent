# Classifying MNIST

_Living report. Every number and figure must trace to an experiment folder (see Appendix)._

## Abstract
Work in progress. "Best" is defined as test accuracy on the official 10k MNIST test set (M00). After week 1: a logistic-regression baseline reaches 92.43 ± 0.06 % test accuracy; the remaining errors are concentrated in class pairs (2/8, 4/9, 3/5/8, 7/9) that are already close in pixel space.

## 1. Introduction
Question: what is the best way to classify MNIST digits, and *why* do different models perform differently? MNIST: 70k 28×28 greyscale digits, 60k train / 10k test. We tune on a fixed-seed 55k/5k train/val split and report test accuracy throughout (M00). Compute: one laptop (M1 Max), ≤ 3 min per experiment.

## 2. Related work
Not yet surveyed systematically. Reference points: LeCun et al. (1998) report 12.0 % error for a linear classifier and < 1 % for convolutional networks; the best published results are ≈ 99.8 %.

## 3. Methods
- **Data** (`tools/data.py`): official IDX files, MD5-verified; inputs scaled to [0,1] and standardised with training-set mean/std.
- **Training** (`tools/train.py`): Adam, cross-entropy, batch 128, final-epoch model evaluated; 3 seeds (init + batch order).
- **Models so far**: nearest class mean (L2 to per-class average image); multinomial logistic regression (`Linear(784,10)`, 7,850 params, no regularisation, lr 1e-3, 20 epochs).

## 4. Results
**Data (001).** Classes balanced within 9–11 %. Train and val are statistically indistinguishable; test is slightly shifted (+1.4 % ink, KS 0.023 > critical 0.015), with the largest per-class shifts for 6, 9, 8 and 0. The closest class-mean pairs are 4–9, 7–9, 3–5, 5–8 and 3–8. 87 principal components capture 90 % of the variance.

**Models.**

| Model | Params | Val acc | Test acc | Train time | Exp |
|---|---|---|---|---|---|
| Nearest class mean | 7,840 | 80.0 % | 81.98 % | < 1 s | 001 |
| Logistic regression | 7,850 | 91.86 ± 0.34 % | 92.43 ± 0.06 % | 3.3 s | 002 |

## 5. Discussion
### Insights
- *Learning vs averaging.* For almost the same parameter count, a learned linear discriminant beats a per-class template by +10.5 pp. The template mostly fails by matching ink amount rather than shape: thin digits get called "1", with 331 such test errors versus 42 for logistic regression. Learning helps most on the most variable classes (5, 8, 2).
- *Linear ceiling.* The residual linear-model errors are the pairs that are already close in pixel space (001). Separating them likely needs non-linear features of stroke topology or position, which is a testable prediction for CNNs.
- *Underfitting.* Train accuracy of 93.4 % is only 1.5 pp above val, so more capacity rather than more regularisation should move accuracy.
- *Unregularised weights* are dominated by rarely-inked border pixels and are therefore poor templates (correlation with class means 0.32–0.43).

### Limitations
- Hyperparameters are untuned. Val accuracy carries ±0.3 pp final-epoch noise and ±0.38 pp sampling SE (5k), so val differences under ~0.4 pp are not meaningful.
- Whether the test shift is about slant or stroke thickness has not been resolved.

## 6. Future work
A capacity ladder: MLP, then a small CNN, then CNN + augmentation. Error analysis per class pair at each rung. Weight decay for logistic regression.

## References
- LeCun, Y., Bottou, L., Bengio, Y., Haffner, P. (1998). Gradient-based learning applied to document recognition. *Proc. IEEE* 86(11).

## Appendix: provenance
| Figure / number | Experiment |
|---|---|
| Class balance, ink, class-mean distances, PCA, split-shift KS | `experiments/001-data-exploration/results/metrics.json` |
| Nearest-class-mean accuracy 80.0 % val / 81.98 % test | 001 (val), 002 (test, recomputed) |
| Logistic regression 92.43 ± 0.06 % test, 91.86 ± 0.34 % val, errors, weights | `experiments/002-logreg-baseline/results/metrics.json` |
