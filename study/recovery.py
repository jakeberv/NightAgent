"""Freeze interrupted runs from their durable evidence without resuming search."""
import json
from pathlib import Path

from .config import StudyConfig
from .events import Accounting, atomic_json, read_events, utc_now
from .selection import initial_summary, select_result


def recover_run(run_dir):
    """Freeze a crashed run from committed events; never grant more search time."""
    run_dir = Path(run_dir)
    if (run_dir / "summary.json").exists():
        return json.loads((run_dir / "summary.json").read_text())
    events = read_events(run_dir / "events.jsonl")
    stopped = next((e for e in reversed(events) if e["type"] == "run_stopped"), None)
    if stopped:
        atomic_json(run_dir / "summary.json", stopped["summary"])
        return stopped["summary"]
    from .problem import ProblemSpec
    data_fingerprint = next((event.get("data_fingerprint") for event in events
                             if event["type"] == "run_started"), None)
    frozen = json.loads((run_dir / "resolved-config.json").read_text())
    config = StudyConfig(**frozen["config"])
    data_fingerprint = frozen.get("data_fingerprint", data_fingerprint)
    problem = ProblemSpec.from_dict(frozen["problem"])
    if problem.fingerprint != frozen["problem_hash"]:
        raise ValueError("Frozen run problem fingerprint does not match")
    summary = initial_summary(config, problem, data_fingerprint)
    if config.lesson_memory:
        summary["lessons"] = []
    accounting = Accounting()
    started_calls = finished_calls = 0
    for event in events:
        if event["type"] == "model_call_started":
            started_calls += 1
        elif event["type"] == "model_call":
            finished_calls += 1
            accounting.add(event.get("usage"))
        elif event["type"] == "lesson_memory" and config.lesson_memory:
            summary["lessons"] = event["lessons"]
        elif event["type"] == "trial_started":
            summary["trials"] += 1
        elif event["type"] == "trial_finished":
            result = event["result"]
            summary["training_seconds"] += result.get("training_seconds", result.get("duration_seconds", 0))
            select_result(summary, result, accounting, config, problem)
    for _ in range(started_calls - finished_calls):
        accounting.add(None)  # An in-flight request may have been billed.
    summary.update(stop_reason="interrupted", elapsed_seconds=events[-1]["elapsed_seconds"] if events else 0,
                   accounting=accounting.snapshot(), recovered_at=utc_now())
    atomic_json(run_dir / "summary.json", summary)
    return summary
