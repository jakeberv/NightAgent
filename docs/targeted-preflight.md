# Targeted five-arm preflight

The revised demo comparison makes lesson memory a standard apprentice capability.
It holds memory on for the supervision, cadence and reflection comparisons and
adds one explicit memory-off control. All supervised arms use Night Science and
initial framing. Literature is disabled in every arm. The historical paid results
below used the former memory policy and do not validate this revised design.

The [21 October revised five-arm run](revised-preflight-results.md) failed only
solo-memory coverage. After the writing-contract correction, the
[targeted solo-only paid revalidation](solo-memory-revalidation.md) passed with
seven fits, seven calls and zero audit errors or warnings. The original failed
receipt is preserved; the other four arms were not paid rerun. This is no combined
current-source five-arm pass. Current launch conditions are in the
[overnight runbook](five-arm-overnight.md).

| Arm ID | Treatment | Declared contrast |
|---|---|---|
| `researcher_alone` | Researcher alone, memory on | Adaptive baseline |
| `frequent` | Review after every attempt, memory on | Frequent minus researcher alone |
| `periodic` | Review after every three attempts, memory on | Periodic minus frequent |
| `periodic_reflection` | Periodic review plus explicit reflection, memory on | Periodic reflection minus periodic |
| `periodic_reflection_no_memory` | Same periodic review and reflection, memory off | Memory-on fourth arm minus this control |

`comparison=apprentice_interactions` freezes these exact arms and their memory
settings. The suite manifest records each arm's unique identity, memory setting,
condition and matched seed. The shared four-core pool permits two concurrent runs;
MPS fits remain serialized. There is one repeat with seed 42 in this preflight.
The existing Fashion-MNIST partitions, search bounds, provider/model and accuracy
targets (85%, 88%, 90%) remain fixed.

The context policy, `active_advice_v1`, keeps initial framing in
`last_supervisor_feedback` until a subsequent review replaces it. Historical
framing remains in `initial_framing`; `active_advice_source` identifies the active
source. Researcher-alone has no advice. Validation still rejects `not_applicable`
when advice exists. Numeric evidence citations expose allowed metric names per
completed trial; `fit_diagnostics` is diagnostic context, not a numeric metric.

Reports show only the four declared contrasts above. The last is directed from
`periodic_reflection_no_memory` to `periodic_reflection`, so reported differences
are memory-on minus memory-off. It explicitly permits the memory difference;
other frozen settings, data identity and matched
repeat/seed requirements still apply. Different targeted configurations remain
separate in aggregates and plots as well as pairs. Legacy comparisons retain
their original grouping behavior. The context policy separates new runs from
historical context variants in matched analysis.

## Reusable full five-arm preflight recipe

This command remains available for a full preflight. It was not repeated for the
first-observation correction, which was revalidated only in the failed solo arm.

Each arm has a 300-second allowance, seven-attempt cap and $2 API guard: **$10 in
combined guards**, with possible final-call overrun. Seven attempts permit reviews
after attempts three and six followed by another experiment. The full suite gets
20 minutes including a three-minute reporting reserve. This is validation-only;
it does not score held-out labels and does not launch the proposed overnight run.

Run from the NightAgent repository, with the existing environment and credential
file. GPU and network access must be available to the process.

```bash
.venv/bin/python -m study suite \
  --config study/fashion-targeted-preflight-config.json \
  --env-file ../AgenticAI2026_Tutorial-3/.env \
  --problem study/problems/fashion-mnist.yaml --data study-data/fashion-mnist \
  --repeats 1 --order-seed 2026 --validation-only --reserve-seconds 180 \
  --deadline "$(.venv/bin/python -c 'from datetime import datetime,timedelta; print((datetime.now().astimezone()+timedelta(minutes=20)).isoformat())')" \
  --output "study-runs/fashion-targeted-preflight-$(date +%Y%m%d-%H%M%S)"
```

## Acceptance

- All five arms complete seven successful fits with complete accounting and
  verified artifact hashes; stops from budget guards leave coverage incomplete.
- Periodic reviews follow attempts three and six, and each is followed by a new
  researcher decision and fit. Frequent reviews follow attempts one through six.
- Explicit reflection occurs only in the two reflection arms, after attempts one
  through six. Each of the first four arms begins empty, saves at least one valid
  lesson and supplies it to a later researcher decision. The fifth control has no
  lesson register, lesson updates or lesson context. Repeats start independently.
- No recurrence of the advice-context error; metric citation repairs and any
  other rejected contracts are separately reported and investigated.
- Five distinct report groups and four declared paired contrasts are present.
  No literature calls or held-out evaluation occurs. Nonattainment remains explicit.
- The full offline suite and independent review pass before the paid run.

This preflight checks execution and interaction coverage. A single repeat does
not establish strategy superiority or causal benefits of advice or memory.
The [21 October revised paid preflight](revised-preflight-results.md) completed
35 fits and 65 calls for $1.665021, but failed researcher-alone memory coverage.
The audit reported two errors from the absent lesson register/delivery and zero
warnings, producing the original **NO-GO**. Its portable receipt preserves that
failed result. The corrected contract passed **961 offline tests** and the
[bounded paid solo revalidation](solo-memory-revalidation.md): seven successful
fits, seven calls, $0.163809 and 92.816 seconds, with 85.4667% best validation
accuracy. Three lesson-update events revised one saved ID; the first note preceded
fit 2 and reached five later researcher contexts. No invalid decision attempt
occurred, and the audit returned zero errors and warnings. All 49 source files
matched the corrected checkout. No full five-arm paid rerun was made.

Launch proceeds from reviewed, merged `main` after final host and visible
key-allowance/effective-budget checks, using the [approved operational funding
gate](workshop-readiness.md#paid-launch-assessment). Independent account balance
visibility is unavailable and is not required for this authorized launch.
Offline scripted scores and this single live trajectory do not establish
strategy benefit.

## Historical fixes and offline verification — 2026-10-20

This section describes the former design: memory off in the first four arms and
on only in the final `periodic_reflection_memory` arm. Its receipts are preserved
as historical records; they are not results for the revised mapping above.

Implemented active initial advice, explicit numeric evidence choices and repair
feedback, and the five-arm suite/report identities with only the four declared
contrasts. Independent review additionally found and verified fixes for mixing
incompatible targeted configurations in aggregate plots and for validating CLI
condition/memory overrides together.

Final full suite: **688 passed in 116.82 seconds**. The offline integration
rehearsal completed five runs and 35 real synthetic-data CPU fits, with the
expected review/reflection schedules, lesson isolation and later delivery,
artifact hashes, five report groups and four matched contrasts. Its evidence is
in `study-runs/targeted-offline-20261020-222604/`. The historical live preflight
used the same Fashion-MNIST data and the former arm-memory mapping.

## Historical live results — 2026-10-20

The [portable real replay](evidence/fashion-demo/demo.md) and
[evidence JSON](evidence/fashion-demo/demo.json) remain available from a fresh
clone as mechanism-demo fallbacks. Current CLI regeneration expects a new suite
with the revised arms; the static historical export is retained as recorded.

Evidence: [HTML report](../study-runs/fashion-targeted-preflight-20261020-222822/report.html)
and [audit summary](../study-runs/fashion-targeted-preflight-20261020-222822/review-summary.json).
The launch exited 0. All five arms completed seven successful fits (35 total:
29 MPS, six CPU), in 448.65 seconds of suite time. There were 68 completed API
calls, 432,636 input/output tokens and **$1.665228** spend, with complete accounting.
All 35 artifact hashes and frozen source hashes verified. Held-out evaluation was
skipped; the report contains five treatment groups and four declared matched
contrasts. Every arm reached 85%; none reached 88% or 90%, and nonattainment and
null conditional costs are correctly retained.

| Arm | Best validation accuracy | API cost | Run seconds |
|---|---:|---:|---:|
| Researcher alone | 87.40% | $0.148371 | 92.42 |
| Frequent supervision | 86.03% | $0.345570 | 179.45 |
| Periodic supervision | 87.40% | $0.329814 | 167.36 |
| Periodic + reflection | 87.50% | $0.399720 | 172.97 |
| Periodic + reflection + memory | 85.40% | $0.441753 | 196.08 |

All expected reviews, reflections and subsequent experiments occurred. Active
advice reached every supervised researcher call. The memory arm began empty,
saved four lesson updates and supplied lessons to four later researcher calls;
the other arms emitted no lesson memory. No advice-context or invalid metric
citation failure recurred. No API transport or fit failure occurred.

One reflection in the memory arm supplied a 340-character lesson scope against
the 240-character limit. Validation rejected it and the model successfully
repaired it on the next call; the rejected response cost $0.027030. Therefore
interaction coverage passes, while the stricter zero-error check does not. This
is a recovered formatting issue, not a blocker for the targeted repeated run.
Keep validation and repair enabled; do not weaken the limit or spend tonight
expanding scope to force perfect model formatting.

These results supported execution coverage of the former policy, not strategy
superiority or validation of the revised memory-default protocol. Some model hypotheses remain speculative and experiments
change multiple settings; the reports mark interpretations unverified and
comparisons confounded where applicable. Treat those as trace material, not
causal claims. Run artifacts are retained locally under `study-runs/` and are
not versioned. At the time of this earlier receipt the overnight run had not
launched. The approximately $18.12 projection extrapolated from these timings
and costs is historical only; the current planning estimate and launch conditions
are recorded in the [solo revalidation](solo-memory-revalidation.md) and
[readiness ledger](workshop-readiness.md).
