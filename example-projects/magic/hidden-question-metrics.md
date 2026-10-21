# Hidden task metric: MAGIC Gamma Telescope

Neither the student nor the supervisor sees this file. Only the end-of-project reviewer does.

- **Metric:** ROC-AUC on the held-out 15% test split, of the classifier (with its preprocessing) that the student presents in `REPORT.md` as its final, best model. Higher is better.
- **Seeds:** if the final model was evaluated with several seeds, use the mean test ROC-AUC across those seeds and give the standard deviation in the notes.
- **Source:** the machine-readable results file (JSON/CSV) of the experiment that `REPORT.md` cites for the final test evaluation. `verified` means the value in the file matches the report.
- **Missing:** `null` if there is no final model, or no test ROC-AUC traceable to a results file (for example, if the test set was never evaluated).
- **Protocol:** `QUESTION.md` requires the test set to stay untouched until the final evaluation. If it was used earlier (for tuning or model selection), still report the value, and say so in the notes.
