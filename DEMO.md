# Workshop demo: accepted study and recorded evidence

**The [corrected five-arm study](docs/five-arm-results.md) is accepted.** All
fifteen runs finished, with 344 verified fits and complete $24.268839 model cost.
The audit passed with zero errors, fifteen repaired-contract warnings and one
terminal-abandonment warning. Use its comparison report and strict recorded
replay for the current demo. The older recordings below remain historical
fallbacks; their failed or different protocols do not describe the current result.

The current five-arm comparison makes lesson memory standard in
`researcher_alone`, `frequent`, `periodic`, and `periodic_reflection`. The explicit
`periodic_reflection_no_memory` control matches the fourth arm with memory off.
Supervision, cadence and reflection comparisons hold memory on; the memory
contrast reports on minus off. Every independent repeat begins with empty lessons.

Generate a three-minute replay from the accepted study's memory-enabled
`periodic_reflection` arm. From the
repository root, with the study environment activated:

```sh
python -m study.demo \
  --suite study-runs/fashion-five-arm-20261021-121920 \
  --output study-runs/fashion-five-arm-demo-20261021 \
  --reference study-runs/fashion-fixed-reference-20261021-000433/trial/result.json
```

`--reference` is optional. It accepts an existing completed `result.json` outside
the adaptive suite, with the fixed configuration derived from the frozen problem,
validation provenance, matching problem/data identities and objective, and a
verified adjacent artifact hash. It reads evidence without unpickling or
retraining. The recorded fixed reference is standard-scaled logistic regression
(`C=1`, `max_iter=300`, seed 42): validation accuracy 81.0333%, one CPU, 4.744
seconds. It is a separate fit outside the matched agent comparison.

Regenerate the comparison report separately from the original saved report:

```sh
python -m study report \
  --output study-runs/fashion-five-arm-20261021-121920 \
  --report-dir study-runs/fashion-five-arm-20261021-121920/monitor/reviewed-report
```

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

The full comparison report contains all three matched seeds and held-out results.
Periodic supervision provided a useful accuracy/throughput balance in this
sample; reflection added cost without a final-accuracy gain, and memory's effect
was mixed across seeds. None reached 90% validation accuracy. The replay proves
an observable advice–experiment–measurement–lesson–context chain, not a causal
memory benefit or general strategy ranking. See [results](docs/five-arm-results.md)
and [readiness](docs/workshop-readiness.md) for the complete limitations.

The earlier [revised paid preflight](docs/revised-preflight-results.md) and
[overnight suite](docs/overnight-results.md) failed acceptance; strict export
must still reject those originals. Scripted offline suites are engineering
rehearsals and must not be presented as language-model strategy evidence.

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
is historical only. The corrected solo revalidation resolved that earlier
coverage failure. The overnight run now provides $22.444005 known cost as a lower bound, with two calls
missing billing; neither result establishes a memory benefit.

If services or compute fail during the workshop, show the saved real replay and
identify it as historical. Do not recreate missing real artifacts or substitute
a scripted fixture as a real run. Three repeats on one split would support a
workshop pilot, not a general ranking or learning across independent runs.

## Manual trace from the failed overnight suite

Label this as a **valid local mechanism trace within a failed suite**, not an
accepted strict export. The [result and portable receipt](docs/overnight-results.md#a-valid-local-mechanism-trace)
provide the saved configurations, accuracy measurements, hashes and journal
locations for `r02-periodic_reflection`:

1. The supervisor's review after trial 9 recommends learning rate 0.007 against
   the 0.005 baseline (journal line 184).
2. The researcher follows the recommendation in executed trial 10 (line 193).
   Both CNN configurations use five epochs, batch size 256, 16 channels, weight
   decay 0.001 and seed 44.
3. Validation accuracy falls from **87.0333% to 86.6667%**, a drop of **0.3667
   percentage points** (line 200).
4. The saved `cnn_learning_rate_boost` lesson is marked `inconclusive` and cites
   the measured trials (line 206). It enters the next researcher context
   (line 208). Delivery does not establish an effect on the following choice.

The suite's aggregate scores include two early stops. All four reported paired
validation-accuracy intervals include zero. Present the trace as a visible
feedback–experiment–measurement–memory loop, with no claim that memory or
supervision improved accuracy. Full independent trace revalidation needs the
original ignored journals and hashed artifacts; the portable receipt remains
readable from a fresh clone.
