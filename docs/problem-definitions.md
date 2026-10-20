# Define a problem without changing the runner

A **problem profile** defines the question, data, scoring, targets and permitted
experiments. A **study configuration** defines model/provider, schedules, repeats
and resource limits. The same five-condition controller runs every supported
problem. Targets are observations; the equal-wall-time study continues after
reaching them.

## Quick start

Create an editable profile and validate it before using API credits:

```bash
.venv/bin/python -m study init-problem --template classification --output problem.yaml
# Edit problem.yaml and put your numeric-feature CSV at its configured path.
.venv/bin/python -m study validate --problem problem.yaml
.venv/bin/python -m study prepare --problem problem.yaml --output study-data/my-problem
.venv/bin/python -m study run --problem problem.yaml \
  --data study-data/my-problem --config study/pilot-config.json \
  --condition periodic_reflection --output study-runs/my-pilot
```

`validate` checks the definition and loads/splits the data in a temporary folder;
it does not fit a model or call OpenRouter. `init-problem` never overwrites a file.
All dataset paths are relative to the profile's directory, not the shell's working
directory. When copying a template, edit its paths for the new location.

For an immediately runnable **offline** example, use the synthetic regression
profile. Model decisions and literature responses are scripted, while training,
scoring, checkpoints and reports are real:

```bash
.venv/bin/python -m study smoke --problem study/problems/regression.yaml \
  --output study-runs/regression-smoke
```

Use a fresh output directory for each run. Smoke checks are not evidence comparing
agent strategies. The default smoke without `--problem` retains the original
synthetic binary-classification example.

## Profile format

YAML and JSON contain the same fields. This headered CSV example uses binary AUC;
change the objective to `accuracy` or `macro_f1` for multiclass classification.

```yaml
schema_version: 1
id: gamma-classification
task: tabular_classification
brief: Distinguish gamma-ray signals from hadronic background.
dataset:
  format: csv
  path: data/events.csv
  header: true
  target_column: class
  positive_class: g
  exclude_columns: [event_id]
evaluation:
  split: {method: stratified_holdout, train: 0.6, validation: 0.2, test: 0.2, seed: 42}
  objective: {metric: roc_auc, direction: maximize}
  additional_metrics: [accuracy, macro_f1]
targets:
  - {name: milestone, value: 0.93}
  - {name: goal, value: 0.95}
search_space:
  preset: tabular_classification_small
  models: [logistic, random_forest, histogram_gradient_boosting]
  preprocessing: [standard, none]
```

| Field | Meaning |
|---|---|
| `id`, `brief` | Stable problem identifier and scientific instructions shown to agents |
| `task` | Trusted classification or regression adapter |
| `dataset` | Local CSV/NPZ source, column/array mapping, or explicit synthetic smoke generator |
| `evaluation.split` | Fixed train/validation/test protocol and split seed |
| `evaluation.objective` | One primary metric and its maximize/minimize direction |
| `additional_metrics` | Secondary measurements, never used to change selection |
| `targets` | Any number of named thresholds on the primary metric; `best` is reserved |
| `search_space` | Allowed model families, preprocessing and optional narrowed parameter bounds |

Classification metrics are `roc_auc` (binary, explicit positive class), `accuracy`,
and `macro_f1`. All maximize. Regression metrics are `rmse` and `mae` (minimize),
and `r2` (maximize, may be negative). AUC 0.95 is not 95% accuracy. Targets use
the metric's units; an RMSE target may exceed 1. A first crossing is `>=` for
maximization and `<=` for minimization. Ties retain the earliest completed trial.

CSV features must currently be numerical and finite. Use `feature_columns` to
select columns, or `exclude_columns` to omit IDs and nonfeatures. The target is
never a feature. Headerless CSV requires explicit `columns`; see MAGIC's profile.
CSV class labels are strings, so quote numeric-looking positive labels when using
AUC. NPZ accepts integer/integral numeric or Unicode categorical labels; unsupported
continuous/byte classification labels fail at validation. Missing values and
categorical features need a future trusted preprocessing extension; they are not
silently imputed or encoded.

The classification preset supplies logistic regression, random forest, and
histogram gradient boosting. Regression supplies ridge, random forest, and
histogram gradient boosting regressors. Scaling is fitted only on training data;
HGB early stopping uses an internal training-only split. Presets fix hard bounds.
You may narrow them, for example:

```yaml
search_space:
  preset: tabular_classification_small
  models: [random_forest]
  preprocessing: [none]
  parameters:
    random_forest:
      n_estimators: {minimum: 50, maximum: 150}
      max_depth: {minimum: 2, maximum: 12}
```

Overrides cannot expand bounds, add unknown estimators/parameters, or contain
Python expressions. Contradictory bounds and enum restrictions fail validation.
Each adapter provides a deterministic fixed reference that respects the narrowed
space. `study reference --problem ... --data ... --output ...` runs it outside the
five conditions. The generic classification reference prefers logistic regression;
the legacy MAGIC reference remains its original fixed HGB pipeline.

## Bundled examples

- [MAGIC](../study/problems/magic.yaml): ten-column telescope data, binary ROC-AUC,
  0.93 milestone and 0.95 stretch threshold. Use `study-data/magic-profile` as the
  new prepared output; the earlier `study-data/magic` belongs to the legacy format.
- [Classification CSV](../study/problems/classification.yaml): arbitrary numerical
  feature columns and named target, using accuracy plus macro-F1.
- [MNIST](../study/problems/mnist.yaml): multiclass digit recognition, accuracy,
  0.95 target, explicit pixel flattening, original test partition preserved.
- [Regression](../study/problems/regression.yaml): synthetic smoke data, minimizing
  RMSE with thresholds 15 and 11, plus MAE/R² measurements.

MNIST is useful because it exercises multiclass labels and image-shaped input.
The initial adapter flattens pixels and uses the bounded classical model menu;
it does not add convolutional networks or pretrained models. Success at 0.95
must be piloted for this menu and the allotted time.

The [official Keras MNIST documentation](https://keras.io/api/datasets/mnist/)
describes the 60,000 training and 10,000 test images. Its
[loader source](https://github.com/keras-team/keras/blob/v3.15.1/keras/src/datasets/mnist.py)
provides this archive and checksum; Keras itself is not required:

```bash
mkdir -p study-data/mnist-source
curl --fail --location \
  https://storage.googleapis.com/tensorflow/tf-keras-datasets/mnist.npz \
  --output study-data/mnist-source/mnist.npz
shasum -a 256 study-data/mnist-source/mnist.npz
# 731c5ac602752760c8e48fbffcf8c3b850d9dc2a2aedcf2cc48468fc17b673d1
.venv/bin/python -m study prepare --problem study/problems/mnist.yaml \
  --output study-data/mnist-profile
```

The NPZ profile names `x_train`, `y_train`, `x_test`, `y_test`; `flatten: true`
turns each image into numerical features. Its split uses `test: official`, with
train/validation fractions 0.8/0.2 applied only to original training data. It
therefore produces 48,000 training, 12,000 validation and 10,000 untouched test
images. No sklearn digits substitution or hidden subsampling occurs. Preparation
stores float64 features and requires several hundred MB of disk/RAM. Full MNIST
fits can take substantially longer than MAGIC; calibrate trial limits locally.

## Frozen evaluation and extensions

Preparation freezes the resolved profile, adapter ID/version, source bytes and
partition fingerprints. Editing targets, the brief, metric, split, columns or
model bounds requires new prepared output. Run/suite preflight checks scientific
identity before provider construction or pricing requests. `--problem` can be
omitted at run time to use the frozen definition. Use the profile's split seed;
`prepare --seed` applies only to legacy `--csv`/`--synthetic` commands.

Both agents receive the same declared task and scoring rules, with their original
role-specific tool restrictions. Workers receive only prepared train/validation
files and a sanitized task description; even an NPZ containing official test data
is not passed to search workers. Test scoring only sees saved selected artifacts
after search. Reports name the actual objective, support arbitrary targets, and
refuse aggregation across incompatible problem/dataset identities or metrics.

Old prepared datasets and ROC-AUC reports remain readable. Legacy `milestone` and
`stretch` study-config fields apply only when no frozen problem profile exists;
profile runs take targets exclusively from the profile.

For a new problem in a supported family, edit a profile. For a genuinely different
family, implement and test a trusted adapter in `study/tasks.py`, register its
metrics/validation in `study/problem.py`, and connect its data preparation and
isolated worker evaluation. The controller consumes only the adapter's tool
schema and results (`metrics`, objective `score`, artifact identity). User YAML
cannot import a module, run shell, or redefine the evaluator.
