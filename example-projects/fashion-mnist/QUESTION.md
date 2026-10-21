# Research question

What is the best way to classify Fashion-MNIST clothing images, and why do different models perform differently on it?

## Context
Fashion-MNIST has 70,000 28x28 greyscale images of clothing in 10 classes (T-shirt/top, trouser, pullover, dress, coat, sandal, shirt, sneaker, bag, ankle boot), with a standard split of 60k for training and 10k for testing. It was designed as a harder drop-in replacement for MNIST: the same format, but models that do almost perfectly on MNIST score clearly lower here. A leaderboard of accuracies is not what I'm after: I want you to try a range of models and understand *why* they perform differently. What do the better models capture that the weaker ones miss, which classes are hard and why, and where do they all still fail?

By "best" I mean the highest accuracy on the official 10k Fashion-MNIST test set. For tuning and model selection, use a fixed-seed split of the training data into 55k for training and 5k for validation. You may report test accuracy throughout the project, but don't use it to choose models or hyperparameters.

## Constraints
- Compute: my laptop: Apple M1 Max, 32 GB RAM (the PyTorch MPS backend may be available). No cloud GPUs.
- Each experiment must run in at most 3 minutes.
- Software: no ML libraries are installed. Set up a project-local `.venv` with Python 3.13 (`/opt/homebrew/bin/python3.13` if present), since PyTorch wheels may not support the newest Python.
- Data: download Fashion-MNIST into `data/` (gitignored); do not commit it.

## Clarifications
<!-- Appended by the student after meetings, only when agreed. -->
