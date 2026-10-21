# Hidden task metric: MNIST

Neither the student nor the supervisor sees this file. Only the end-of-project reviewer does.

- **Metric:** classification accuracy (%) on the official 10,000-image MNIST test set, of the model the student presents in `REPORT.md` as its final, best model. Higher is better.
- **Seeds:** if the final model was trained with several seeds, use the mean test accuracy across those seeds and give the standard deviation in the notes.
- **Source:** the machine-readable results file (JSON/CSV) of the experiment that `REPORT.md` cites for that model. `verified` means the value in the file matches the report.
- **Missing:** `null` if there is no final model, or no test accuracy traceable to a results file.
- **Protocol:** `QUESTION.md` forbids using the test set to choose models or hyperparameters. If it was used that way, still report the value, and say so in the notes.
