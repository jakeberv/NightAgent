# M00 — 2026-10-19 (kickoff)

## Results presented
- None (kickoff). Student restated the question, proposed six candidate meanings of "best" (accuracy, accuracy-vs-cost, data efficiency, robustness, simplicity, trustworthiness) and a first week of baselines across a complexity ladder.

## Supervisor feedback
- "best is test accuracy"
- The 55k/5k train/validation split for tuning is good.
- "I want to test a range of models and get insights on why they perform differently"
- Each experiment should take no longer than 3 minutes to run.
- First-week actions: visualise the dataset, do data exploration, understand differences in the data, make a basic baseline model and training script.

## Questions and answers
- Q (student): Which definition of "best"?
  A (supervisor): Test accuracy.
- Q (student): Is a held-out 5k validation split from the 60k training set acceptable for all tuning?
  A (supervisor): Yes.
- Q (student): What do you already believe / what do you want out of this?
  A (supervisor): Test a range of models and get insights on why they perform differently.
- Q (student): Are default budgets OK?
  A (supervisor): Each experiment ≤ 3 minutes. (Weekly cap ~1 hour of compute proposed by student; not objected to.)
- Q (student): "Differences in the data" — between classes, or between splits?
  A (supervisor): All of those.
- Q (student): Is a single logistic regression enough as the basic baseline?
  A (supervisor): Yes, logistic regression.
- Q (student): Keep the test set untouched until a final evaluation, or report test accuracy along the way?
  A (supervisor): Test accuracy can be used throughout the project. (Student noted this supersedes the "final evaluation only" constraint in QUESTION.md; tuning and model selection still use the validation split.)

## Agreed actions
1. Explore MNIST — done when an experiment folder contains sample grids, class balance, per-class mean/variance images, a class-similarity analysis, a train/val/test distribution comparison (pixel statistics, class frequencies), and a written summary — budget 1–2 experiments, ≤ 3 min each.
2. Reusable tools — done when `tools/` has a data loader with a fixed-seed 55k/5k split and a train/eval script logging val and test accuracy, wall-clock time and parameter count, each with docstrings — budget pilots only.
3. Logistic regression baseline — done when trained over 3 seeds with val and test accuracy reported as mean ± std, plus a confusion matrix — budget 1–2 experiments, ≤ 3 min each.

Weekly compute cap: ~1 hour.

## Memory updates
- supervisor.md: + values understanding *why* models perform differently, not just ranking them (project scope).
- lessons.md: none.
- pending.md: none.

## Addendum (after meeting, 2026-10-19)
- Supervisor: "for now, let's make the first week quicker (no more than 10 mins runtime) - as we are demoing you right now". Week-1 total compute capped at ≤ 10 min; scope: week 1 only. Actions unchanged.
