# Workshop demo: current protocol and recorded fallback

The current five-arm comparison makes lesson memory standard in
`researcher_alone`, `frequent`, `periodic`, and `periodic_reflection`. The explicit
`periodic_reflection_no_memory` control matches the fourth arm with memory off.
Supervision, cadence and reflection comparisons hold memory on; the memory
contrast reports on minus off. Every independent repeat begins with empty lessons.

After a new suite has passed the current independent audit, generate a three
minute replay from its memory-enabled `periodic_reflection` arm. From the
repository root, with the study environment activated:

```sh
python -m study.demo \
  --suite study-runs/YOUR_NEW_MEMORY_DEFAULT_SUITE \
  --output /tmp/nightagent-workshop-demo \
  --reference study-runs/fashion-fixed-reference-20261021-000433/trial/result.json
```

`--reference` is optional. It accepts an existing completed `result.json` outside
the adaptive suite, with the fixed configuration derived from the frozen problem,
validation provenance, matching problem/data identities and objective, and a
verified adjacent artifact hash. It reads evidence without unpickling or
retraining. The recorded fixed reference is standard-scaled logistic regression
(`C=1`, `max_iter=300`, seed 42): validation accuracy 81.0333%, one CPU, 4.744
seconds. It is a separate fit outside the matched agent comparison.

The exporter writes `demo.md` (timed presenter script) and `demo.json`
(measurements, configurations, context-delivery evidence, journal locations, line
numbers and input hashes). Choose output separate from the suite and reference.
Generation makes no provider calls, trains or evaluates no model, and leaves the
suite untouched. A passing strict audit is required; missing journals, changed
artifacts, incomplete accounting or missing lesson delivery stop export with
exit status 2. The exporter selects an executed comparison cited in a later
lesson and confirms that the lesson entered a subsequent researcher context.
It does not select the best score. `offline_fixture` and `unverified_provider`
labels distinguish scripted or unverified records from real provider evidence.

A new offline suite with scripted decisions and real synthetic-data CPU fits can
verify this pipeline. Present it as engineering rehearsal, not language-model
strategy evidence. The [revised paid preflight](docs/revised-preflight-results.md)
completed but failed solo-memory acceptance; strict demo export must reject that
suite. The [corrected solo revalidation](docs/solo-memory-revalidation.md) passed,
but does not supply a new accepted five-arm suite. Use the historical fallback
until an overnight suite passes audit; consult [readiness](docs/workshop-readiness.md)
for operational status.

## Historical real replay available from a fresh clone

The verified [presenter replay](docs/evidence/fashion-demo/demo.md) and
[portable evidence JSON](docs/evidence/fashion-demo/demo.json) are retained in Git
as the real mechanism-demo fallback. They record the earlier preflight, which
used memory off in the first four arms and on only in its final
`periodic_reflection_memory` arm. They are historical evidence and do not
validate the current memory-default comparison. Current CLI regeneration expects
a new suite using the revised arms; use this saved export directly for the old
recording. Independent revalidation of that export requires its original ignored
suite journals and hashed model artifacts.

Use the historical script with these limits visible:

1. **0:00–0:45:** Show the former five arms: researcher alone 87.4%, frequent
   86.0333%, periodic 87.4%, periodic plus reflection 87.5%, and its memory arm
   85.4%. Seven fits each gave 35 fits, 68 calls and $1.665228 recorded cost.
2. **0:45–1:30:** Show the recommendation, reflection and trial 5's `modified`
   response. The researcher says the CNN suggestion had already been tested and
   chooses the reflection's random-forest comparison. Interpretations remain
   unverified.
3. **1:30–2:15:** Compare trials 3 and 5. Only `max_features` changes, from `sqrt`
   to `log2`; validation accuracy falls from 85.4% to 84.8333%, or 0.5667 points.
4. **2:15–3:00:** Show the scoped lesson citing both trials and its delivery
   before trial 6. The 85% target was reached at 64.239 seconds, before the first
   lesson at 88.845 seconds. That crossing cannot establish memory benefit.

Retain the historical-source and repaired-contract warnings. This is one matched
repeat and a mechanism demonstration. A delivered lesson shows what entered a
later context; it does not prove that the lesson caused an action or improved
performance. The approximately $18.12 projection once derived from this preflight
is historical only. The corrected solo revalidation refreshes the provisional cost estimate and
resolves the observed coverage failure; it does not establish a memory benefit.

If services or compute fail during the workshop, show the saved real replay and
identify it as historical. Do not recreate missing real artifacts or substitute
a scripted fixture as a real run. Three repeats on one split would support a
workshop pilot, not a general ranking or learning across independent runs.
