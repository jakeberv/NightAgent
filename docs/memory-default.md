# Lesson memory is a standard apprentice capability

The current study defaults lesson memory on in `StudyConfig` and every runnable
study preset. A researcher can retain bounded, evidence-linked lessons without a
supervisor or an explicit reflection step. Each independent run begins with an
empty register; lessons survive the recent-history window and recovery within
that run, and never transfer between matched repeats.

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
the new memory prompts can change usage in four arms. A new bounded paid pilot
must establish a current planning estimate before paid launch. Offline scripted
rehearsal tests operation and memory delivery; it does not measure model strategy
or establish a memory benefit.
