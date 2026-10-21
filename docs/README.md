# Documentation guide

Start with the [project overview](../README.md). This guide identifies the purpose
of each document so that setup instructions, scientific methods, evidence and
development history have distinct homes.

## Explore or present

| Document | Purpose |
|---|---|
| [Project goals](project-goals.md) | Apprentice vision, workshop scope, research questions and limits |
| [Workshop specification](../SPEC.md) | Compact submission describing the task, tools, evaluation and demo |
| [Workshop milestones](workshop-milestones.md) | Official requirements mapped to deliverables, evidence and remaining gaps |
| [Demo script](../DEMO.md) | Presentation sequence and honest fallback using saved real evidence |
| [Readiness](workshop-readiness.md) | Dated verification results, known limits and prerequisites for a paid launch |
| [Evaluation cases](evaluation-cases.md) | Eight named engineering acceptance cases and how to run them |
| [Revised paid preflight result](revised-preflight-results.md) | Real-model measurements, failed memory coverage, diagnosis and launch decision |
| [Fixed reference](fixed-reference.md) | Non-agent classifier result and reproducible receipt |

## Run the controlled study

Follow [getting started](getting-started.md) for an offline first run, then the
[operator entry point](../study/README.md) for provider setup and execution.

| Document | Purpose |
|---|---|
| [Study reference](study-reference.md) | Commands, contracts, reports, logs and recovery details |
| [Workshop protocol](workshop-protocol.md) | Current treatments, controls, outcomes and interpretation rules |
| [Targeted preflight](targeted-preflight.md) | Bounded five-arm live check before committing to a larger run |
| [Five-arm overnight](five-arm-overnight.md) | Current paid recipe, frozen settings and independent audit |
| [Memory policy](memory-default.md) | Default lesson memory, explicit opt-out and the matched control |
| [Configuration index](configurations.md) | Presets and which comparison each serves |
| [Problem definitions](problem-definitions.md) | Data, scoring, targets and allowed experiments in reusable profiles |
| [Fashion preparation and calibration](fashion-pilot.md) | Dataset preparation, neural setup, hardware calibration and dated earlier pilots |

The protocol defines the scientific comparison. The JSON configurations and
problem profile define executable settings. Launch recipes supply repeat counts
and commands. Readiness records observations; it does not change the experiment.

## Contribute or inspect provenance

- [CI and dependencies](ci.md): reproducible environments and regression checks.
- [Event format](event-format.md): trace and artifact contract.
- [Tutorial attribution](tutorial-attribution.md): workshop components and adaptations.
- [Conversational prototype](../nightagent/README.md): its separate setup, permissions and meeting workflow.
- [History and earlier studies](archive/README.md): design notes, dated verification logs, earlier comparisons and implementation plans.

The [shared design document](https://docs.google.com/document/d/1tBVSIyVEs3PdngYK7uHr1yEs5l3R0f5kC1OOjMMFqqA/edit)
mirrors the spec and current protocol for workshop collaboration. Its original
concept tabs remain labeled historical. Maintain the repository documents first,
then sync those two shared tabs; keep detailed setup and status in their linked
guides. The milestone checklist records submission uncertainty separately from
the presence of these deliverables.
