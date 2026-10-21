# Lesson memory is a standard apprentice capability

The current study defaults lesson memory on in `StudyConfig` and every runnable
study preset. A researcher can retain bounded, evidence-linked lessons without a
supervisor or an explicit reflection step. Each independent run begins with an
empty register; lessons survive the recent-history window and recovery within
that run, and never transfer between matched repeats.

When memory is enabled, a researcher whose register is empty must include at
least one scoped, cited observation note in the existing `lesson_updates` field
on each decision after a completed fit supplies a citable validation measurement,
while the register remains empty. Each response still permits at most two
updates. The first decision, decisions without citable completed evidence, and
histories containing only failed fits are exempt. A researcher's note is saved
when a proposal is admitted for a new fit. Reused or deadline-skipped proposals
do not save it, so the requirement continues while the register is empty. Once
it contains a lesson, further updates are optional. Memory-off behavior is
unchanged.

The note is part of the ordinary researcher decision, with bounded repair within
the existing turn and resource budgets before another fit can start. It adds no
reflection phase or separate memory call. A simple factual observation is enough;
the researcher need not invent an insight or assert a causal conclusion.
Existing citation checks, generated factual finding/scope, unverified original
interpretations and `supported`, `inconclusive` or `superseded` statuses remain
unchanged.

The Fashion-MNIST `apprentice_interactions` comparison fixes five treatments:

| Arm ID | Supervision / reflection | Lesson memory |
| --- | --- | --- |
| `researcher_alone` | Ordinary planning; no supervisor | On |
| `frequent` | Night Science review after each attempt | On |
| `periodic` | Night Science review after every three attempts | On |
| `periodic_reflection` | Periodic review and explicit researcher reflection | On |
| `periodic_reflection_no_memory` | Same review and reflection as the preceding arm | Off |

All supervised arms share initial framing. Literature remains disabled. The
supervision, cadence and reflection contrasts hold memory on. The memory
contrast is `periodic_reflection` minus `periodic_reflection_no_memory`, so a
positive validation-accuracy difference favors memory on. For minimized metrics,
cost and time, a negative difference favors memory on.

`--no-lesson-memory` explicitly disables memory for a single `run` or the earlier
`schedules` and `supervisor_strategies` comparisons; `--lesson-memory` explicitly
enables it. These flags do not redefine the five-arm suite's fixed mapping. The
suite manifest records each arm's condition, memory setting, repeat and seed.

The scientific task, Fashion partitions, accuracy targets, model/provider,
600-second overnight allowances, fit limits, spending guards and resource policy
are unchanged. Use the [current protocol](workshop-protocol.md) and
[launch recipe](five-arm-overnight.md).

The earlier paid preflight used memory only in its final
`periodic_reflection_memory` arm. Its [recorded real replay](evidence/fashion-demo/demo.md)
is retained as historical mechanism evidence and cannot validate this revised
comparison. Its approximately $18.12 overnight projection is historical only:
the new memory prompts can change usage in four arms. The
[revised paid preflight](revised-preflight-results.md) now records actual usage
and a provisional projection. Its 21 October 2026 **NO-GO** remains historical
evidence: all 35 fits and 65 calls completed for $1.665021, but optional updates
were omitted throughout the solo run, failing memory coverage. That receipt
remains unchanged.

The corrected contract passed the [targeted paid solo revalidation](solo-memory-revalidation.md):
seven fits and seven calls for $0.163809. The first note was saved before fit 2
and delivered to five later researcher contexts; the audit found zero errors and
zero warnings. The other four arms were not rerun, so this is no combined
current-source five-arm pass. This establishes memory writing and delivery in one
run; it does not establish strategy benefit.
