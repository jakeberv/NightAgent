# Research question

Can we distinguish gamma-ray signal events from hadronic cosmic-ray background in the MAGIC telescope data, which classifier and preprocessing do it best, and why?

## Context
The MAGIC Gamma Telescope dataset ([UCI](https://archive.ics.uci.edu/dataset/159/magic+gamma+telescope)) contains 19,020 Monte Carlo–simulated events recorded by a ground-based imaging Cherenkov telescope. Each event has ten numerical features describing the image of the particle shower (length, width, size, concentration, asymmetry, alpha, distance and so on), and a label: gamma (signal, about 65%) or hadron (background, about 35%).

By "best" I mean the highest ROC-AUC on a held-out test set. AUC measures how well a classifier ranks gammas above hadrons, not the percentage classified correctly. As reference points: reaching a validation AUC of 0.93 is my milestone, and 0.95 is a stretch goal that I have not seen demonstrated within the search space below. A quick pilot reached roughly 0.93–0.94 with tree-based models.

I care as much about *why* as about the number. Is performance limited by preprocessing or by classifier capacity? Which features carry the signal, and what does that say about the physics of the showers?

## Constraints
- Compute: my laptop: Apple M1 Max, 32 GB RAM. No cloud GPUs.
- Each experiment must run in at most 3 minutes. A pilot on similar hardware took about 0.2–0.6 s for histogram gradient boosting and about 5 s for a 200-tree random forest per fit and validation prediction.
- Splits: a single fixed-seed, stratified split into 70% train, 15% validation and 15% test, created once and saved. Fit models and preprocessing on the training set only, and use validation for all tuning and model selection. Keep the test set untouched until the final evaluation.
- Search space: start with scikit-learn's logistic regression, random forest and histogram gradient boosting, with bounded iterations, tree counts and depth, and early stopping on training data where supported. Ask me before adding other model families.
- Software: set up a project-local `.venv` with Python 3.13 (`/opt/homebrew/bin/python3.13` if present), since some libraries may not support the newest Python yet.
- Data: download the dataset into `data/` (gitignored); do not commit it.

## Clarifications
<!-- Appended by the student after meetings, only when agreed. -->
