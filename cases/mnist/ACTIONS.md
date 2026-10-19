# Actions

## Agreed at latest meeting (M00, 2026-10-19)
1. Explore MNIST — done when an experiment folder contains sample grids, class balance, per-class mean/variance images, a class-similarity analysis, a train/val/test distribution comparison (pixel statistics, class frequencies), and a written summary — budget 1–2 experiments, ≤ 3 min each.
2. Reusable tools — done when `tools/` has a data loader with a fixed-seed 55k/5k split and a train/eval script logging val and test accuracy, wall-clock time and parameter count, each with docstrings — budget pilots only.
3. Logistic regression baseline — done when trained over 3 seeds with val and test accuracy reported as mean ± std, plus a confusion matrix — budget 1–2 experiments, ≤ 3 min each.

Weekly compute cap: ~1 hour. **Week 1 override (supervisor, post-M00): total runtime ≤ 10 min, because of a live demo.**

## Week goals
Week 1 (started 2026-10-19). Total compute ≤ 10 min (demo override).

1. **G1 — Environment + data.** `.venv` (Python 3.13 for wheel compatibility), pinned `requirements.txt`, MNIST IDX files in `data/`. Done when `tools/data.py` loads train 55k / val 5k / test 10k with a fixed seed and checksum-verified downloads.
2. **G2 — Training tool.** `tools/train.py`: generic PyTorch train/eval loop logging val + test accuracy, wall-clock, parameter count to JSON. Done when a 1-epoch pilot runs. (Action 2)
3. **G3 — Exp 001 data exploration.** Sample grids, class balance per split, per-class mean/std images, class-similarity (distance between class means + nearest-mean confusion), train/val/test pixel-statistic comparison, written summary. Done when README has prediction, results, conclusion. Runtime target < 1 min. (Action 1)
4. **G4 — Exp 002 logistic regression.** Softmax regression, 3 seeds, val/test mean ± std, confusion matrix, weight visualisation. Runtime target < 3 min total. (Action 3)
5. **G5 — Write-up.** REPORT.md + `meetings/M01-brief.md`.

Small labelled initiative: visualise the learned logistic-regression weight templates and compare them to the class-mean images from 001 — directly serves the "why do models differ" goal at ~zero cost.
