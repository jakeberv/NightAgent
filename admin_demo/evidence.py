"""Audit one solo run and extract a small, portable account of its behavior."""
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def collect(root):
    # Reuse the study's per-run checks, without claiming five-arm acceptance.
    from study.audit import _Audit
    from study.config import StudyConfig
    from study.demo import _reference
    from study.records import load_events
    from study.reasoning import validate_contract
    from study.workshop_eval import load_cases

    root = Path(root).resolve()
    run = root / "runs" / "researcher_alone"
    summary = read(run / "summary.json")
    config = StudyConfig(**read(run / "config.json"))
    events = load_events(run / "events.jsonl", policy="strict")
    engineering = read(root / "engineering" / "results.json")
    provider = read(run / "provider.json")
    audit = _Audit(root)
    manifest = {key: summary[key] for key in (
        "problem", "problem_hash", "data_fingerprint", "objective", "target_definitions")}
    manifest.update(postrun_policy="validation_only", provenance=provider.get("runtime", {}))
    audit.provenance(manifest)
    audit.run({"run_id": "researcher_alone", "arm": "researcher_alone", "repeat": 0}, config, manifest)
    audit.check(config.condition == "researcher_alone" and config.lesson_memory
                and config.trial_cap == summary["trials"] == 7
                and config.allowance_seconds == 300 and config.dollar_cap == 1
                and summary["stop_reason"] == "trial_cap", "demo_limits",
                "Expected seven completed solo fits with memory, a 300-second allowance and $1 guard.")
    expected_cases = {c["id"]: c["pytest_nodes"] for c in load_cases()}
    actual_cases = engineering.get("cases", [])
    audit.check(engineering.get("passed") is True and len(actual_cases) == len(expected_cases) == 8
                and {c["id"] for c in actual_cases} == set(expected_cases)
                and all(c["status"] == "passed" and c.get("pytest_nodes") == expected_cases[c["id"]]
                        for c in actual_cases),
                "engineering", "All eight engineering cases must pass.")
    reference = {}
    try:
        reference = _reference(root / "reference" / "result.json", manifest, root / "runs")
    except (ValueError, OSError, KeyError) as exc:
        audit.issue("reference", str(exc))

    history, trace, memory_events, deliveries = [], [], [], []
    starts, decisions = {}, {}
    context = {}
    for line, event in enumerate(events, 1):
        kind = event["type"]
        if kind == "model_call_started":
            context = json.loads(event["messages"][1]["content"])
            if context.get("lessons"):
                deliveries.append({"before_trial": len(history) + 1, "line": line,
                                   "lesson_ids": [x["id"] for x in context["lessons"]]})
        elif kind == "decision_contract" and event.get("valid"):
            errors = validate_contract(event["contract"], "researcher", history, memory=True)
            audit.check(not errors, "citations", "; ".join(errors))
        elif kind == "decision":
            decisions[event["trial_id"]] = event
        elif kind == "trial_started":
            starts[event["trial_id"]] = (event, line, context.get("lessons", []))
        elif kind == "lesson_memory":
            memory_events.append({"after_trial": len(history), "line": line, "lessons": event["lessons"]})
        elif kind == "trial_finished":
            fit = event["result"]
            start, start_line, lessons = starts[fit["trial_id"]]
            calls = decisions[fit["trial_id"]]["message"].get("tool_calls", [])
            requests = [c for c in calls if c.get("function", {}).get("name") == "run_analysis"]
            audit.check(len(requests) == 1, "tool_call", "Each fit needs one recorded run_analysis request.")
            if requests:
                args = json.loads(requests[0]["function"]["arguments"])
                args.pop("intent", None)
                audit.check(args == start["config"], "tool_call", "Executed configuration differs from the model request.")
            intent = start["intent"]
            trace.append({"trial": fit["trial_id"], "tool": "run_analysis", "arguments": start["config"],
                          "summary": intent["summary"], "hypothesis": intent.get("hypothesis", ""),
                          "evidence": intent["evidence"], "status": fit["status"],
                          "score": fit.get("score"), "metrics": fit.get("metrics", {}),
                          "elapsed_seconds": fit.get("elapsed_seconds"),
                          "lessons_received": [x["id"] for x in lessons],
                          "request_line": start_line, "result_line": line,
                          "artifact_sha256": fit.get("artifact_hash")})
            history.append(fit)

    audit.check(bool(memory_events) and bool(deliveries), "memory", "Need a saved lesson and subsequent delivery.")
    scripted = config.provider == "offline" or any(
        (e.get("response", {}).get("raw") or {}).get("offline") for e in events if e["type"] == "model_call")
    files = [run / name for name in ("config.json", "events.jsonl", "summary.json", "provider.json")]
    files += [root / "reference" / "result.json", root / "engineering" / "results.json"]
    return {
        "schema_version": 1, "passed": not audit.errors, "source_kind": "scripted" if scripted else "live",
        "recorded_at": events[0]["timestamp"], "model": config.model, "device": config.device,
        "metric": summary["objective"]["metric"], "best_score": (summary.get("best") or {}).get("score"),
        "elapsed_seconds": summary["elapsed_seconds"], "accounting": summary["accounting"],
        "stop_reason": summary["stop_reason"], "reference": reference, "trace": trace,
        "memory": {"updates": memory_events, "deliveries": len(deliveries), "delivery_events": deliveries},
        "engineering": [{"id": c["id"], "status": c["status"]} for c in engineering.get("cases", [])],
        "audit": {"errors": audit.errors, "warnings": audit.warnings, "runs": audit.runs},
        "provenance": {"problem_hash": summary["problem_hash"], "data_fingerprint": summary["data_fingerprint"],
                       "admin_source_sha256": {p.name: digest(p) for p in Path(__file__).parent.glob("*.py")
                                                if not p.name.startswith("test_")},
                       "study_source_sha256": manifest["provenance"].get("source_sha256", {}),
                       "evidence_sha256": {str(p.relative_to(root)): digest(p) for p in files}},
    }
