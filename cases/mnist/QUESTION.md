# Research question

What is the best way to classify MNIST handwritten digits?

## Context
MNIST (70,000 28x28 greyscale handwritten digits, 10 classes; standard 60k train / 10k test split) is a classic benchmark.
This project is a proof-of-concept case study for the NightAgent student/supervisor workflow: the process of
finding out what "best" should mean, and the evidence behind the answer, matter as much as the final number.
The supervisor has deliberately left "best" undefined: clarify it in the kickoff meeting.

## Constraints
- Compute: local laptop: Apple M1 Max, 32 GB RAM (PyTorch MPS backend may be available). No cloud GPUs.
- Software: no ML libraries are installed yet; set up a project-local `.venv` (the system Python is 3.14).
- Data: download MNIST into `data/` (gitignored); do not commit it.
- ~~Keep the official test set held out for final evaluation only.~~ SUPERSEDED at M00 (see Clarifications).

## Clarifications
<!-- Appended by the student after meetings, only when agreed. -->
- **"Best" = test accuracy** on the official 10k MNIST test set. (M00)
- **Splits:** a fixed-seed 55k/5k train/validation split of the 60k training set; all tuning and model selection use validation only. (M00)
- **Test set use:** test accuracy may be reported throughout the project (supersedes "final evaluation only" above). (M00)
- **Goal:** test a range of models and gain insight into *why* they perform differently. (M00)
- **Budget:** each experiment ≤ 3 minutes wall-clock; ~1 hour of compute per week. (M00)
