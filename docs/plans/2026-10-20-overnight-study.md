# Overnight study implementation

> Dated engineering record. For current scope, instructions and review status,
> use the [documentation guide](../../docs/README.md). Later decisions may supersede this plan.

Approved direction: implement the updated Experimental design tab in the
existing `experiment/overnight-openrouter` checkout, based on dev-ben2 e285fad.
Source: [Google Doc](https://docs.google.com/document/d/1tBVSIyVEs3PdngYK7uHr1yEs5l3R0f5kC1OOjMMFqqA/edit?tab=t.60m8hjogcisp).
The retrieved source is preserved in `docs/experimental-design-source.txt`.

## Global constraints

Keep the conversational Claude SDK runner intact. Add a standalone `study`
package using direct OpenRouter Chat Completions. Exactly five conditions,
equal run wall time, matched model/provider/settings/data/seeds/search space.
All attempts count toward cadence and trial caps; no kickoff review.
Reviews follow attempts 1,2,... (frequent) or 3,6,... (periodic). Reflection
is a separate call between trials in the final two conditions. Only condition
five's supervisor may browse, only during reviews. No agent gets shell,
filesystem, model artifacts, test data, or arbitrary code execution.

Use immutable prepared train/validation/test partitions, bounded sklearn
pipelines, train-only preprocessing and killable trial processes. Freeze
completed artifacts before the deadline; milestone crossings do not stop.
Count all calls and attempts, preserving unknown costs as unknown. No paid
experiment during implementation. Single-host sequential runs avoid resource
confounds. Resume interrupted runs by freezing them as interrupted, never
renewing their allowance or repeating test evaluation.

## Tasks and ownership

1. Provider and literature (`study/provider.py`, `study/literature.py`,
   `tests/test_provider.py`, `tests/test_literature.py`): async OpenRouter with
   raw accounting, explicit pinning, deadline-bounded requests, no hidden
   retries; bounded literature search/fetch with evidence provenance.
2. Scientific evaluator (`study/science.py`, `study/worker.py`,
   `tests/test_science.py`): prepare dataset/splits, schema and pure bounded
   pipelines, subprocess trials, artifacts, fixed reference and once-only
   held-out evaluation.
3. Controller/integration (root agent): configuration, event store, role
   prompts/tools, schedule, accounting, checkpoint selection, suite deadline,
   CLI, offline fake model, tests.
4. Reporting/docs: artifact reports, plots, tutorial attribution, setup and
   pilot instructions, after the controller event contract is settled.
5. Review and verification: component review, offline end-to-end run, full
   tests, independent whole-change review, fix findings.

## Shared interfaces

All modules use Python 3.12+. Runtime dependencies: httpx, numpy, sklearn,
joblib, jsonschema, matplotlib. Tests use pytest and asyncio.run (no plugin).

`OpenRouter(model, provider, temperature=0, max_tokens=2048, api_key=None,
transport=None)` exposes
`async complete(messages, tools, *, timeout: float) -> dict`.
Return normalized `message` (OpenAI assistant object), `usage` (raw dict or
null), `id`, `provider`, `model`, `raw`. Raises `ProviderError` with
`details` dict for status/response/unknown accounting. No retry inside
provider; controller logs and budgets each attempt. Tool JSON uses OpenAI
function schema. `aclose()` closes owned HTTP client.

`LiteratureClient` exposes `async search(query, *, timeout)` and
`async fetch(url, *, timeout)` returning JSON-serializable evidence.
Search uses public scholarly API with source URLs; fetch supports only
public HTTP(S), caps bytes and text, rejects nonpublic destinations and
redirects. Controller counts calls under one per-review cap.

`science.prepare_dataset(output: Path, *, csv_path: Path | None = None,
synthetic: bool = False, seed: int = 42) -> dict` provisions either a local
MAGIC-format CSV or explicit synthetic smoke data; never auto downloads.
Stores `train.npz`, `validation.npz`, `test.npz`, `manifest.json`. Includes
fingerprints, split protocol, counts, feature names; test stats excluded
from agent-facing `project_info(data_dir)`.
`science.ANALYSIS_SCHEMA` is strict JSON schema for a bounded pipeline config.
`science.validate_config(config)` rejects unsupported keys/values.
`async science.run_trial(data_dir, trial_dir, config, *, seed, timeout)
-> dict` returns status completed/failed/timeout, validation_auc on success,
artifact path and artifact hash, elapsed_seconds, error on failure.
No test access in trial subprocess. Strip secrets from worker environment,
limit BLAS threads. Artifacts written atomically. Parent reaps process group
on timeout/cancellation. Controller adds id/elapsed and excludes late returns.
`science.evaluate_selected(data_dir, run_dir, selections: dict[str,dict])
-> dict` evaluates each unique selected artifact once, persists cache
atomically; selections contain artifact, artifact_hash, validation_auc.
`science.fixed_reference(data_dir, output_dir, *, seed, timeout)` is async,
uses a frozen histogram gradient boosting config, outside five conditions.

Events JSONL: `type`, `run_id`, `timestamp`, `elapsed_seconds`, plus payload.
Required types: run_started, model_call, tool_call, trial_started,
trial_finished (result dict), review, reflection, selection, run_stopped.
`summary.json` includes condition, repeat, allowance_seconds, stop_reason,
elapsed_seconds, trials, best/milestone/stretch selection objects or null,
accounting {known_cost, cost_complete, input_tokens, output_tokens,
cached_tokens, reasoning_tokens, token_usage_complete}, and config.
Selection objects include trial_id, elapsed_seconds, validation_auc,
artifact, artifact_hash, accounting at completion. Test results are a
separate file, never included in role context.

## Pilot rulings

MAGIC and a stratified 60/20/20 split are configurable starting choices,
not validated final study decisions. Parameters and budgets are frozen in
each suite manifest. Model and provider must be explicit for live runs.
Malformed model decisions consume wall time and are logged; bounded retry
streaks prevent infinite no-progress loops. Unknown billing stops live runs
by default, with an explicit exploratory override that marks totals unknown.
Memory is rebuilt with the same bounded recent-trial window for every call,
independent of review cadence. Feedback and reflection retained only as
condition-specific treatments. Study deadline and reporting reserve are
checked before launching every full run; an insufficient window aborts
instead of shortening one condition's allowance.
