# Workshop demo: a recorded experiment loop

Use a three minute replay of the strict, recorded five-arm Fashion-MNIST preflight. The selected `periodic_reflection_memory` arm covers review, reflection, a scoped lesson, and later context delivery. Its 85.4% best validation accuracy is below several other arms; selection is for feature coverage.

The verified [presenter replay](docs/evidence/fashion-demo/demo.md) and
[portable evidence JSON](docs/evidence/fashion-demo/demo.json) are included in Git
for presenting from a fresh clone. Regeneration requires the original ignored
suite and reference artifacts; the checked-in export can be read without them.

From the repository root, with the study environment activated:

```sh
python -m study.demo \
  --suite study-runs/fashion-targeted-preflight-20261020-222822 \
  --output /tmp/nightagent-workshop-demo \
  --reference study-runs/fashion-fixed-reference-20261021-000433/trial/result.json
```

`--reference` is optional. It accepts an existing completed `result.json` outside the adaptive suite. It requires the fixed configuration derived from the frozen problem, validation-split provenance, matching problem/data fingerprints and objective, and a verified adjacent model artifact hash. It reads the evidence without unpickling or retraining. The recorded fixed reference is standard-scaled logistic regression (`C=1`, `max_iter=300`, seed 42): validation accuracy 81.0333%, one CPU, 4.744 seconds. It is a separate fit, outside the matched agent comparison.

The command writes `demo.md` (timed presenter script) and `demo.json` (measurements, configurations, exact context-delivery evidence, relative journal locations, line numbers, and input hashes). Output must be separate from the suite and reference. Generation makes no provider calls, needs no credentials, performs no training or evaluation, and leaves the suite untouched. The existing strict audit must pass before export; missing journals, changed artifacts, incomplete accounting, or missing lesson delivery stop the command with exit status 2. Historical `source_changed` and repaired-contract warnings remain visible.

Follow the generated script:

1. **0:00–0:45:** Show all five arms: researcher alone 87.4%, frequent 86.0333%, periodic 87.4%, periodic plus reflection 87.5%, and memory 85.4%. Each completed seven fits: 35 fits, 68 calls, $1.665228 recorded cost in total. Planning occurs in every arm; supervised arms share initial framing. Literature tools were disabled.
2. **0:45–1:30:** Show the supervisor's recorded recommendation, the latest reflection, and trial 5's `modified` response. The researcher says the CNN recommendation had already been tested and selects the reflection's random forest comparison. Model hypotheses and expectations remain unverified.
3. **1:30–2:15:** Compare the saved trial 3 and trial 5 configurations. Only `max_features` changes, from `sqrt` to `log2`. Validation accuracy changes from 85.4% to 84.8333%, a decrease of 0.5667 percentage points on this split.
4. **2:15–3:00:** Show the lesson citing both trials, its explicit scope, and its presence in the researcher context before trial 6. The 85% target was reached at 64.239 seconds, before the first lesson at 88.845 seconds. That crossing cannot establish a memory benefit.

The exporter selects the first chronological executed comparison with baseline and result cited together in a later delivered lesson. It does not search for the best score. The JSON labels provider records separately from `offline_fixture` or `unverified_provider` records. Scripted `FakeModel` fixtures test replay plumbing; they are not experimental strategy evidence.

This is one matched repeat and a mechanism demonstration. It does not establish that supervision, reflection, or memory improves performance. A scoped lesson and confirmed delivery show what entered the next context; they do not prove the lesson caused the next action or an improvement.

If live services or compute fail during the workshop, use `demo.md` and the suite's existing `report.html`. The replay is portable, but independent revalidation still requires the original suite records and hashed model artifacts. If those artifacts are unavailable, do not recreate them or present a scripted fixture as a real run; use a previously verified export and identify it as recorded evidence.
