# Configurable problem definitions

> Dated engineering record. For current scope, instructions and review status,
> use the [documentation guide](../../../docs/README.md). Later decisions may supersede this plan.

User approved the proposed problem-definition/task-adapter architecture and requested a checkpoint commit first. Checkpoint: 39f8fd6. User additionally requests MNIST if scientifically valid; include it as multiclass classification with accuracy, preserving its official test partition.

Goal: select a problem, dataset, targets, permitted experiments and validation protocol without modifying orchestration. Keep OpenRouter, the five schedules, wall-time control, recording and post-run evaluation reusable. New task families require reviewed Python adapters; a YAML file never supplies executable code. No paid calls or overnight comparison in implementation.

Problem YAML/JSON: schema_version=1, id, task (tabular_classification or tabular_regression), brief (text), dataset, evaluation {split, objective {metric,direction}, additional_metrics}, targets [{name,value}], search_space {preset, models, parameters optional, preprocessing optional}. Reject unknown fields, nonfinite values, duplicate target names, incompatible task/metric/direction, invalid splits or model choices. Dataset paths resolve relative to profile, never cwd. Targets are named and generic; no hardcoded 0.93/0.95 in new paths. Study budget files contain no required scientific choices. Legacy behavior remains available for old prepared data and historical reports.

CSV supports headers, explicit column names for headerless data, target column, feature inclusion/exclusions, positive class for binary AUC; numeric features only for initial adapters, missing/nonfinite data rejected clearly. NPZ supports named feature/target arrays, optional separate official test arrays, and explicit image flattening. No pickle loading. Preserve official MNIST test set; split validation out of original training only. Support synthetic smoke classification, multiclass and regression without downloads. Local data only; docs give official MNIST acquisition reference. A data limit/subset, if supported, must be explicit and recorded; never silently replace MNIST with sklearn digits.

Classification metrics: accuracy, macro_f1, binary roc_auc (explicit positive label). Regression metrics: rmse, mae, r2. Metric registry fixes maximize/minimize direction and valid bounds. Model space bounded by trusted task preset; overrides may narrow existing bounds, not add arbitrary classes/arguments. Classification menu logistic/random_forest/histogram_gradient_boosting; regression ridge/random_forest/histogram_gradient_boosting. Preprocessing fit only on training. Include a fixed reference per adapter.

New trial result: status, metrics dict, score (configured objective), artifact/hash, timing/config/seed. Historical validation_auc retained only for roc_auc compatibility. Selection uses configured direction, earliest completion for ties, arbitrary named target crossings, never stops on target. Summary includes objective, target_definitions, target_selections, best, frozen problem+hash. Legacy milestone/stretch remain compatibility aliases. Generic test results: metrics, score, status/hash; optional test_auc for legacy roc_auc. Only frozen selected artifacts reach hidden postrun evaluator, with existing at-most-once cache.

Reports label metrics/direction, generic targets/crossings, no invented AUC or 0..1 axis for RMSE/R2. Reject or clearly partition incompatible objective/problem comparisons; all scheduled runs retained, unknown costs/crossings preserved. Old reports readable.

User workflow: init-problem template, validate --problem (load/validate data without fitting or API), prepare --problem --output, run/suite --problem --data --config --output. Run with a changed profile against frozen data must fail before any provider/network call. Frozen manifest stores resolved definition+hash, data/split fingerprints, adapter id/version. Brief and tools generated from the same resolved definition used by evaluator.

Examples: MAGIC CSV, generic headered classification CSV, MNIST npz multiclass accuracy .95 target, synthetic regression RMSE minimization. Offline CLI end-to-end tests demonstrate custom classification, regression and MNIST-shaped fixtures (explicitly not real MNIST evidence).
