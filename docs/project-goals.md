# Project goals and workshop scope

Updated 21 October 2026. The current memory-default implementation is under
review in [PR 14](https://github.com/jakeberv/NightAgent/pull/14); main still
contains the previous memory policy.

## The original goal

NightAgent asks whether an AI researcher can retain feedback and evidence,
change its behavior, and become a more useful collaborator over a research
project. The scientist supplies a broad brief, permitted methods, evaluation
rules and resource limits. A researcher chooses experiments; a separate
supervisor frames questions, critiques evidence and recommends follow-up work.
Scientific questions can evolve within the brief. Useful negative results and
justified uncertainty count as progress.

Apprentice behavior and scientific outcomes need separate evaluation. Retaining
corrections, questioning advice with reasons and avoiding repeated mistakes are
useful apprentice behaviors. Correct measurements, sound comparisons,
reproducible artifacts and supported conclusions establish scientific quality.
A high classifier score alone does not show learning from feedback.

The [original design discussion](archive/design-notes.md) preserves earlier
proposals; the [current protocol](workshop-protocol.md) defines the implemented
workshop experiment.

## What the workshop implements

The workshop tests whether structured supervision improves experiment choices
enough to justify its time and API cost. Fashion-MNIST supplies one classification
problem with frozen partitions, metrics, permitted configurations and limits.
Agents choose experiments and interpret validation evidence. The harness trains
classifiers, checks citations, saves artifacts and enforces limits. Official test
data stays hidden during search.

The output is an experiment history, evidence-linked reviews and lessons, a
selected model artifact and an HTML comparison. The language model's weights
stay fixed; a tool trains the classifiers it chooses.

| Original ambition | Current implementation | Evidence still needed |
| --- | --- | --- |
| Autonomous research within a scientist's brief | Researcher selects bounded experiments; supervised arms receive framing and later reviews. | A revised live comparison and human inspection of decisions. |
| Retain feedback and evidence | Scoped lessons cite recorded measurements and survive the recent-history window within a run. | Whether those lessons improve later choices or outcomes. Delivery alone does not establish benefit. |
| Change behavior after feedback | Decision contracts record whether advice was followed, modified or rejected and which configuration ran next. | Whether the response was scientifically useful, with trace review and matched outcomes. |
| Improve over a longer research project | A separate conversational prototype stores project files across meetings. The controlled study resets lessons in every independent repeat. | Controlled tests of transfer between sessions, projects or tasks; these have not been performed. |

Five arms compare researcher alone, frequent supervision, periodic supervision,
periodic supervision plus reflection, and the same final arm without lesson
memory. The first four use memory. The [launch recipe](five-arm-overnight.md)
fixes three matched repeats: **15 scientific runs**, each with 600 seconds and a
shared resource policy.

The [conversational Claude SDK prototype](../nightagent/README.md) is another route
toward the original ambition. Its open-ended meetings and project memory have
different permissions, stopping rules and evaluation from `python -m study`.
Results from either application need their own evidence.

## What the evidence currently supports

The revised implementation's scripted checks establish software behavior,
artifact handling and lesson delivery. The [readiness ledger](workshop-readiness.md)
records their receipts and the [measured fixed reference](fixed-reference.md).

The [saved real-model replay](evidence/fashion-demo/demo.md) shows an
advice → configuration → result → lesson → later-context sequence under the
former memory policy. The revised live pilot, overnight comparison and held-out
Fashion scoring remain pending. Neither the historical replay nor the scripted
checks establish memory benefit, a winning supervision strategy or transfer
between independent runs.

## Next steps toward the goal

First finish the workshop package: specification, runnable baseline, checkable
engineering cases, labeled replay and presentation. The
[milestone checklist](workshop-milestones.md) separates artifacts from submission
and remaining work.

Then, after review and a new bounded live pilot, refresh the cost estimate and
verify funding before the matched comparison. Freeze search before held-out
scoring, audit the evidence, and inspect a small trace sample for useful advice
and appropriate lesson scope. Report uncertainty across the three repeats.

Longer-term work can test retained learning across independent sessions and new
tasks, with fresh comparisons and separate apprentice/science scorecards.
Reinforcement learning, MCP tools, generated tools and additional researchers are
possible extensions. They are not prerequisites for the current workshop demo.
