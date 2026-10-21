# Workshop requirements, evidence and remaining work

Checked 21 October 2026 against the organizer's
[Milestone II brief](https://drive.google.com/file/d/1vlHVag4J-dssSvxz-hcrxj6bapHHnNV8/view)
and [Tutorial 1 slides](https://drive.google.com/file/d/1hTG9cqrhanhREHccTFzOOatgGPplvZgW/view).
This is a team checklist for workshop delivery. The [project goals](project-goals.md)
explain the broader research ambition; the [protocol](workshop-protocol.md)
defines this experiment.

The revised memory-default code is under review in
[PR 14](https://github.com/jakeberv/NightAgent/pull/14). Main retains the earlier
policy. Available artifacts and recorded checks do not establish organizer
acceptance or completion by a deadline.

## Milestones

Deadlines below use local workshop time at Blue Mountain, Ontario
(`America/Toronto`), in October 2026. The brief gives weekdays and times without
an explicit timezone. It specifies the later milestones and the spec template;
Tutorial 1 also lists the first GitHub push.
No separate Milestone III–V brief was found in the
[official materials folder](https://drive.google.com/drive/folders/1y0gK2IkM6dWqQ0o0usbPz0vYh8Y-DVdT)
or the milestone-file search during this review. The table therefore uses the
requirements actually available, rather than assuming additional submission rules.

| Milestone and deadline | Organizer requirement | Repository evidence | Status and gap |
| --- | --- | --- | --- |
| I — Mon 19, 11:30 | First GitHub push. | [Team repository](https://github.com/jakeberv/NightAgent) and versioned source. | Repository exists. This review does not establish the time or acceptance of the original submission. |
| II — Mon 19, 17:00 | Root `SPEC.md`, one page/about 400 words, covering task, agent decisions, tools/data, baseline, evaluation, demo, risks/limits/roles. | [SPEC.md](../SPEC.md), [protocol](workshop-protocol.md), [goals](project-goals.md). | The revised concise spec covers all seven sections, including an input/output example, historical fallback, main risk and token limit. Tool count, spend and ownership need the checks below. |
| III — Tue 20, 17:00 | Simplest baseline that runs end to end and can be compared with the agent. Data access must already work. | [Measured fixed classifier](fixed-reference.md), [portable reference receipt](evidence/fashion-fixed-reference.json), [study commands](../study/README.md), historical real-agent replay and current offline rehearsals. | A fixed non-agent baseline has run on the frozen Fashion partitions: 81.03% accuracy, 4.74 seconds, zero model calls. Its receipt is dated Wed 21; it does not prove Tuesday completion. Researcher alone is the matched adaptive baseline; its revised live run remains pending. |
| IV — Wed 21, 11:00 | Evaluation script; 5–20 cases with known answers or pass/fail checks; declared metric, repeat count and comparison. Estimate total cost and check remaining key allowance before this milestone. | [Eight named cases](evaluation-cases.md), [runner](../study/workshop_eval.py), [case mapping](../study/evaluation_cases.json), [current acceptance receipt](evidence/memory-default-acceptance.json). | Recorded result: 8/8 cases, 52 underlying checks. The scientific comparison has not run under the revised policy. Its current paid-cost estimate and funding check remain open. |
| V — Wed 21, 13:00 | Demo script describing one example and what the audience should see. | [DEMO.md](../DEMO.md), [saved presenter replay](evidence/fashion-demo/demo.md), [portable evidence](evidence/fashion-demo/demo.json). | A three-minute historical real-model replay is available, with source/citation pointers and limitations. A revised live demo requires new accepted evidence; the saved replay is the fallback. |
| Team presentations — Wed 21, 16:30 | Team presentation; format is unspecified in the available brief. | Specification, reference, engineering receipts and replay supply source material. | Final presentation materials and presenter assignments are not recorded in this repository. Prepare them and rehearse the fallback before presenting. |

The read-only audit of the organizer's
[Group Work tracker](https://docs.google.com/spreadsheets/d/1tHX6_E5Tb3KsYNAo6dc44_9Zo0LmB9vldKbx-lvEWCo/edit)
found Team 5 on row 7: Milestone 2 (`E7`) says `fixed`; Milestone 3 (`F7`) is
blank. No tracker update was made. These cells do not certify later milestones
or submission timing; the team should confirm their status with the organizers.

## Check the spec against the actual template

| Template detail | Current coverage and bounded follow-up |
| --- | --- |
| User, input/output and one concrete example | Covered: the revised spec gives “compare clothing classifiers” → verified model, measurements, decisions, lessons and report. |
| Why an agent? | The researcher chooses configurations using earlier evidence; review cadence, tools and evaluation are a fixed workflow. Keep that division explicit. |
| 3–6 tools, with inputs/outputs and data-access status | The spec declares one `run_analysis` interface: bounded configuration in, validation metrics/artifacts out. Context and recent results arrive automatically. This departs from the template's 3–6-tool range; organizer acceptance remains unconfirmed. Adding redundant tools solely to reach a count would not improve the experiment. Data access is established by the reference and real fits. |
| Accessible data and simplest baseline | Real Fashion fits and the verified fixed reference establish local access. Link the reproduction command and expected reference output. Keep the fixed reference separate from the equal-allowance researcher-alone baseline. |
| 5–20 checkable cases, metric, repeats and comparison | Eight named engineering cases meet the requested case-count range. Each reports pass/fail. Run the package once for engineering acceptance; the scientific design separately has five arms × three matched repeats, with validation accuracy primary and cost/runtime plus secondary metrics reported. |
| Demo and fallback | Covered: the spec explicitly names the historical saved replay as fallback. `DEMO.md` labels its former memory policy and traces a scoped lesson into a later context without claiming benefit. |
| Risks, limits, expected spend and roles | Covered: main risk of unsupported conclusions, fit/attempt/resource limits, 2,048 output tokens per call and $75 nominal guards. Expected paid spend remains pending a new pilot. Component owners remain unconfirmed; record agreed owners for harness/memory, tools/data and evaluation/demo. |

## Two tutorial components, without unnecessary scope

Tutorial 1 requires at least two tutorial components. NightAgent combines its
narrow tool interface, explicit model/tool loop and JSONL evidence traces with
Tutorial 2's reflection and retained lessons. The
[tutorial attribution](tutorial-attribution.md) maps these ideas to implementation
sources. Tutorial 4 informs reliability and coordination accounting.

The Milestone II brief makes reinforcement learning optional and says MCP tools
can be added later. Neither is required for this delivery. Reflection and context
memory leave language-model weights unchanged. Learning across independent runs
is a separate future experiment.

## Evidence and launch boundaries

The [readiness ledger](workshop-readiness.md) and
[verification receipt](evidence/memory-default-verification.json) are the
canonical record of regression checks, CPU rehearsals and real MPS fits. Their
scripted decisions establish engineering behavior. The saved real preflight
uses the former memory policy; its spending projection is obsolete for the
revised prompts. A new live pilot, overnight comparison and Fashion held-out
scoring remain pending.

Before paid evaluation, apply the organizer's cost rule: measured cost per run ×
cases × repeats. The offline engineering package uses no paid calls. For the
scientific matrix, estimate each current arm's measured run cost × three repeats,
then add the pilot and any reporting or failure allowance. Check the total
against current key allowance and separately verify underlying account funding.
A successful key-limit check does not verify the account balance. Keep keys and
raw account metadata private, as the
[participant handout](https://drive.google.com/file/d/14nFqy21Teb6Y2xF5I_FhiuFDfhNWuEy4/view)
requires. Fifteen $5 guards sum to $75 and can be exceeded by an in-flight call;
they are not a spend forecast or a billing ceiling.

## Remaining work in order

1. Review the concise spec against the gaps above, confirm component owners and
   organizer/tracker status, and prepare the presentation from verified evidence.
2. Finish review of the revised implementation. Before any paid launch, run a
   new bounded live pilot, refresh the estimate, and verify funding and the host.
3. If the team proceeds, run the frozen 15-run comparison, freeze selections,
   score held-out artifacts once, and require complete accounting and a passing
   independent audit. Report all three matched pairs and uncertainty.
4. Present the available evidence and its limits. Use the labeled historical
   replay if the new comparison is incomplete. Evaluate transfer across sessions
   and tasks later under the [broader project goals](project-goals.md).
