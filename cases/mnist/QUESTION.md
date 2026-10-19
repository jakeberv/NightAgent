# Research question

What is the best way to classify MNIST handwritten digits?

## Context
MNIST (70,000 28x28 greyscale handwritten digits, 10 classes; standard 60k train / 10k test split) is a classic benchmark.
This project is a proof-of-concept case study for the NightAgent student/supervisor workflow: the process of
finding out what "best" should mean, and the evidence behind the answer, matter as much as the final number.
"Best" is deliberately undefined here: clarify it with your supervisor at the kickoff meeting.

## Constraints
- Compute: local laptop: Apple M1 Max, 32 GB RAM (PyTorch MPS backend may be available). No cloud GPUs.
- Software: no ML libraries are installed; set up a project-local `.venv`. Use Python 3.13 (`/opt/homebrew/bin/python3.13` if present): PyTorch wheels may not support the system Python 3.14.
- Data: download MNIST into `data/` (gitignored); do not commit it.

## Clarifications
<!-- Appended by the student after meetings, only when agreed. -->
