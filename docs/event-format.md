# Study journal format

`events.jsonl` is the committed evidence stream for each run. New records carry
`schema_version: 1`. This version governs both the event envelope and its
embedded trial result. The contracts and parser live in
[`study/records.py`](../study/records.py).

Each record has a nonempty string `type`. The journal writer also records
`run_id`, a UTC `timestamp`, and wall-clock `elapsed_seconds`. Payloads remain
specific to their event type. JSON numbers must be finite. Format validation
does not establish scientific correctness: the audit separately checks metrics,
accounting, artifacts, selections, seeds, and interaction coverage.

Important payloads:

| Event | Payload contract |
| --- | --- |
| `trial_finished` | `result` object with a positive integer `trial_id` and status `completed`, `failed`, `timeout`, or `late`. Optional `metrics` and `config` are objects. The runner supplies seed, timing, diagnostics, and artifacts when available. |
| `model_call` | Status `completed`, `failed`, or `cancelled`; usage remains unknown when unavailable. |
| `*_contract` | Boolean `valid`; rejected contracts retain errors, and successful repairs are separate records. |
| Other events | A valid envelope plus the event-specific payload. New event names do not require a format-version bump unless their shared representation changes. |

The writer validates before appending and flushes committed records. Unversioned
records can be read when they already have the current structure. No legacy
layout translation or reconstruction of missing observations is performed.
Unsupported explicit versions fail validation.

## Reader policies

`load_events(path, policy=..., warnings=...)` defines how each consumer handles
incomplete evidence:

| Policy | Consumer | Invalid records |
| --- | --- | --- |
| `strict` | Acceptance audit | Reject any malformed, truncated, nonfinite, or unsupported record. An empty journal also fails the audit. |
| `recover` | Interrupted-run recovery | Permit only a syntactically unfinished final append without a newline; committed corruption and unsupported formats fail. Recovery freezes observed work and never grants more search time. |
| `report` | Reports | Keep valid records and surface a warning for each rejected record, including file and line. Missing measurements remain unknown. |

Reporting success is not acceptance. Use `study audit --output ROOT` or include
`--audit` in the suite launch to verify the full comparison. Treat format warnings
as evidence to investigate before using a report's scientific conclusions.
