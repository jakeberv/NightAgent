# Study configuration presets

The active demo uses [`fashion-five-arm-overnight-config.json`](../study/fashion-five-arm-overnight-config.json) and the [five-arm launch recipe](five-arm-overnight.md). Earlier presets remain runnable inputs for their documented experiments; a filename containing “overnight” or “smoke” does not select the current protocol or make model calls free.

This index covers every `study/*config.json`. Values below are per run, before CLI overrides. `run` executes the preset's single `condition`; `suite` expands its `comparison` into matched arms. All presets use OpenRouter model `anthropic/claude-sonnet-4.5`, serving provider `anthropic`, temperature 0, 2,048 maximum output tokens, base training seed 42, a 12-trial recent-history window and one model retry. Night Science supervision is the default unless a comparison selects a different strategy. Unknown billing stops execution in all presets.

| Preset | Purpose / status | `suite` comparison | `run` condition | Time / attempts / API guard | Fit timeout; model timeout | Resources; lesson memory |
|---|---|---|---|---|---|---|
| [`fashion-five-arm-overnight-config.json`](../study/fashion-five-arm-overnight-config.json) | **Active demo launch**; [recipe](five-arm-overnight.md) | `apprentice_interactions` (5 arms) | `researcher_alone` | 600 s / 1,000 / $5 | 45 s; 60 s | MPS, 4 shared cores; final arm only |
| [`fashion-targeted-preflight-config.json`](../study/fashion-targeted-preflight-config.json) | Active short acceptance preflight; [recipe/results](targeted-preflight.md) | `apprentice_interactions` (5 arms) | `researcher_alone` | 300 s / 7 / $2 | 45 s; 60 s | MPS, 4 shared cores; final arm only |
| [`fashion-comprehensive-smoke-config.json`](../study/fashion-comprehensive-smoke-config.json) | Earlier broad **paid**, validation-only coverage recipe; [four-suite recipe](comprehensive-smoke.md) overrides comparison/memory | `schedules` (5 arms) | `researcher_alone` | 300 s / 4 / $2 | 45 s; 60 s | MPS, 4 shared cores; off by default |
| [`fashion-five-minute-config.json`](../study/fashion-five-minute-config.json) | Earlier short, three-arm validation-only pilot; [command](../study/README.md#earlier-fashion-supervisor-style-pilot) | `supervisor_strategies` (3 arms) | `researcher_alone` | 105 s / 12 / $1 | 45 s; 60 s | MPS, 4 shared cores; off |
| [`fashion-overnight-config.json`](../study/fashion-overnight-config.json) | Earlier three-arm overnight design; **superseded for the demo**; [historical recipe](fashion-pilot.md#frozen-overnight-comparison) | `supervisor_strategies` (3 arms) | `researcher_alone` | 900 s / 1,000 / $5 | 45 s; 60 s | MPS, 4 shared cores; off |
| [`fashion-pilot-config.json`](../study/fashion-pilot-config.json) | Earlier single-run Fashion feasibility pilot; [guide](fashion-pilot.md) | `schedules` (5 arms) | `periodic_reflection` | 300 s / 12 / $3 | 45 s; 60 s | MPS, 4 shared cores; on for every suite arm |
| [`magic-pilot-config.json`](../study/magic-pilot-config.json) | Earlier single-run MAGIC feasibility pilot; [guide](magic-pilot.md) | `schedules` (5 arms) | `periodic_reflection` | 300 s / 12 / $3 | 60 s; 60 s | `auto`, no shared core pool; off |
| [`pilot-config.json`](../study/pilot-config.json) | Original general/MAGIC schedule baseline; [guide](../study/README.md#five-schedule-comparison) | `schedules` (5 arms) | `researcher_alone` | 900 s / 1,000 / $20 | 60 s; 90 s | `auto`, no shared core pool; off |
| [`supervisor-comparison-config.json`](../study/supervisor-comparison-config.json) | Earlier general/MAGIC supervisor-style design; [guide](../study/README.md#three-condition-supervisor-comparison) | `supervisor_strategies` (3 arms) | `researcher_alone` | 900 s / 1,000 / $20 | 60 s; 90 s | `auto`, no shared core pool; off |

The API guard is checked between requests; an in-flight request can exceed it. Trial caps count launched attempts, including failed/timed-out fits; repeated equivalent proposals do not launch another fit. Time allowances include model calls, repairs, tools, queue waiting and failures. Deadline admission can stop a run before its allowance when another useful interaction and fit no longer fit.

## Comparison modes

- `apprentice_interactions`: researcher alone → frequent review → periodic review → periodic review plus reflection → periodic review plus reflection and lesson memory. All supervised arms use Night Science; literature is disabled. Suite construction fixes memory off for the first four arms and on for the final arm, independently of the base JSON's `lesson_memory`. Reports declare four adjacent contrasts.
- `supervisor_strategies`: researcher alone, frequent standard supervision, and frequent Night Science supervision. Reflection/literature are disabled; the base memory setting applies to every arm.
- `schedules`: researcher alone, frequent review, periodic review, periodic review plus reflection, and periodic review plus reflection and literature. The selected supervisor style and base memory setting apply to every arm. Literature belongs only to the final arm's scheduled supervisor reviews.

Supervised arms share an initial framing step. Frequent review follows every attempt; periodic review follows every three. All arms receive recent experiment history. Lesson memory is a separate bounded register, empty at each run's start, and never transfers between runs. `--lesson-memory`/`--no-lesson-memory` can override a base setting for the earlier comparison modes; they do not redefine the declared five-arm memory contrast.

## What the JSON does not freeze

Dataset, objective, splits, model search bounds and targets come from the [problem profile](problem-definitions.md) and prepared data. Use the current [`fashion-mnist.yaml`](../study/problems/fashion-mnist.yaml) and its matching prepared directory for the active demo. Config files do not embed a dataset, repeat count, suite deadline, reporting reserve, order seed or `--validation-only` policy: those belong to the CLI recipe and frozen suite manifest.

The active overnight recipe uses three repeats (15 runs), seeds 42–44, two concurrent runs sharing four CPU cores, one MPS fit at a time, a two-hour deadline and 1,200-second postrun reserve. Its guards sum to $75, not a guaranteed billing ceiling. Held-out evaluation follows frozen search. Preflight recipes pass `--validation-only` to skip held-out scoring; the JSON alone does not do so.

`study/fashion-calibration-configs.json` is a list of fixed local trial configurations for `study calibrate`, not a study-run preset. `python -m study smoke` uses built-in scripted decisions and synthetic data without a preset or paid calls. It is distinct from the paid comprehensive smoke recipe above.
