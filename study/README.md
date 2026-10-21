# Controlled study runner

The controlled runner uses direct OpenRouter Chat Completions and bounded
scientific tools. For a first experience, follow
[Try NightAgent locally](../docs/getting-started.md): scripted decisions, real
CPU fits and an HTML report, with no API key or dataset download.

The current paid demo is the
[five-arm Fashion-MNIST comparison](../docs/five-arm-overnight.md). Memory is on
in `researcher_alone`, `frequent`, `periodic` and `periodic_reflection`;
`periodic_reflection_no_memory` matches the fourth arm with memory off. All
supervised arms use Night Science and initial framing; literature is disabled.
Independent runs start with empty lessons. The first three contrasts hold memory
on, and the memory contrast reports on minus off. See the
[memory contract](../docs/memory-default.md).

Use the [operator reference](../docs/study-reference.md) for command behavior,
credentials, evidence contracts, live controls, reporting and recovery. The
[configuration index](../docs/configurations.md) identifies every preset's
purpose, actual comparison and budget. Earlier experiment recipes remain
available as [earlier workflows](../docs/study-reference.md#earlier-experiment-recipes).
The separate [conversational Claude SDK prototype](../nightagent/README.md) has
its own setup and is not required for the study runner.

## Setup and offline verification

Follow the [local getting-started guide](../docs/getting-started.md) for Python
3.12, the locked CPU installation, the explicit `apprentice_interactions` smoke
command and opening its report. Developer checks and platform-specific neural
dependencies are in [CI](../docs/ci.md) and
[named engineering evaluation cases](../docs/evaluation-cases.md).

## Define a problem and pilot it

The [problem-definition guide](../docs/problem-definitions.md) covers editable
YAML/JSON profiles, CSV/NPZ data, targets, classification/regression examples and
frozen evaluation. See [prepared-data behavior](../docs/study-reference.md#problems-prepared-data-and-equivalent-trials)
and the [predeclared Fashion reference](../docs/fixed-reference.md).

### Legacy MAGIC workflow and feasibility pilot

Use the [MAGIC pilot guide](../docs/magic-pilot.md) for the profile-backed recipe.
The [legacy workflow and measured feasibility results](../docs/study-reference.md#legacy-magic-workflow-and-feasibility-pilot)
are retained for earlier `--csv` data and historical runs.

## Evidence, hypotheses, and run-local lessons

The [evidence and lesson contracts](../docs/study-reference.md#evidence-hypotheses-and-lesson-contracts)
describe decisions, supervisor framing/reviews, citations, repair budgets and
bounded lesson memory. These checks verify recorded measurements; generated
interpretations do not become causal conclusions. The
[event-format reference](../docs/event-format.md) defines the evidence journal.

### Earlier Fashion supervisor-style pilot

The [earlier three-arm five-minute recipe](../docs/study-reference.md#earlier-fashion-supervisor-style-pilot)
remains available for review-style experiments. For the active five-arm protocol,
use the [targeted preflight](../docs/targeted-preflight.md) and
[overnight runbook](../docs/five-arm-overnight.md). Both live workflows require
credentials and funding; a new bounded pilot must precede the revised overnight
launch. Historical paid results do not validate its memory policy or cost estimate.

## Coordination and matched-comparison reports

See [reports and matched comparisons](../docs/study-reference.md#reports-and-matched-comparisons)
for accounting, target attainment, pairing rules, difference direction and
uncertainty limits. Rebuilding a report reads saved evidence without model calls.

## Configure OpenRouter

Read [credentials and paid execution](../docs/study-reference.md#credentials-and-paid-execution)
before a live launch. Model/provider configuration and API cost guards are
separate from [live display and log controls](../docs/study-reference.md#live-display-and-logs).

## Earlier five-schedule comparison

The [earlier schedule reference](../docs/study-reference.md#earlier-five-schedule-comparison)
describes the literature arm and its bounded tools. This is `comparison: schedules`,
not the current `apprentice_interactions` mapping.

## Overnight suite

The [current five-arm runbook](../docs/five-arm-overnight.md) owns the active
15-run launch, resource policy, deadlines and acceptance audit. General
[deadline and shared-resource behavior](../docs/study-reference.md#limits-and-shared-resources)
is documented separately from the recipe.

### Three-condition supervisor comparison

See the [earlier review-style comparison](../docs/study-reference.md#three-condition-supervisor-comparison)
for `supervisor_strategies`, its three arms and offline verification.

### Five-schedule comparison

See the [earlier five-schedule reference](../docs/study-reference.md#earlier-five-schedule-comparison)
and [MAGIC all-five recipe](../docs/magic-pilot.md#all-five-strategies).

## Artifacts, evaluation, and recovery

See [artifacts, held-out scoring and recovery](../docs/study-reference.md#artifacts-evaluation-and-recovery)
for saved files, selection rules, interruption handling and offline reports/audits.
Recovery freezes observed work and does not start more search.

### Fashion-MNIST and strategy efficiency

The [Fashion pilot guide](../docs/fashion-pilot.md) covers optional PyTorch/MPS
setup, data preparation and local calibration. Interpret efficiency using
[attainment and accounting limits](../docs/study-reference.md#reports-and-matched-comparisons)
and the [current protocol](../docs/workshop-protocol.md).
