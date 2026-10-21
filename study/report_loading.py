"""Read frozen report artifacts and normalize current journal evidence.

All report filesystem reads live here. Invalid event lines remain visible in the
shared warnings list; summary selections never replace missing trial evidence.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .records import load_events


@dataclass
class RunArtifacts:
    folder: Path
    summary: dict
    events: list[dict]
    tests: dict
    postrun: dict
    data_fingerprint: str | None
    events_available: bool


@dataclass
class ReportArtifacts:
    runs: list[RunArtifacts]
    metadata: dict
    warnings: list[str]
    postrun: dict
    is_suite: bool


def read_object(path: Path, warnings: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("expected a JSON object")
        return value
    except (OSError, ValueError) as exc:
        warnings.append(f"Could not read {path}: {exc}")
        return {}


def read_events(folder: Path, warnings: list[str]) -> list[dict]:
    path = folder / "events.jsonl"
    if not path.exists():
        return []
    try:
        return load_events(path, policy="report", warnings=warnings)
    except OSError as exc:
        warnings.append(f"Could not read {path}: {exc}")
        return []


def trials_from_events(events: list[dict], selected_results: dict) -> list[dict]:
    """Use controller-frozen result completion times, not journal append times."""
    metadata = {str(selected["trial_id"]): {key: selected[key] for key in
                ("artifact", "artifact_hash", "accounting") if key in selected}
                for selected in selected_results.values() if selected is not None}
    trials = {}
    for event in events:
        if event["type"] == "trial_finished":
            result = event["result"]
            identity = str(result["trial_id"])
            trials[identity] = {**metadata.get(identity, {}), **result, "trial_id": identity}
    return list(trials.values())


def selections(summary: dict) -> dict:
    return {**(summary.get("target_selections") or {}), "best": summary.get("best")}


def data_fingerprint(summary: dict, events: list[dict]):
    """Only frozen run identity and its run-start record establish provenance."""
    candidates = [summary.get("data_fingerprint")]
    candidates.extend(event.get("data_fingerprint") for event in events
                      if event["type"] == "run_started")
    known = {value for value in candidates if value is not None}
    if len(known) > 1:
        raise ValueError("Incompatible data fingerprints in frozen run records; report each data snapshot separately.")
    return next(iter(known), None)


def load_run(path: Path, summary: dict, cache: dict, warnings: list[str]) -> RunArtifacts:
    events = read_events(path.parent, warnings)
    observed_ids = {str(event["result"]["trial_id"]) for event in events if event["type"] == "trial_finished"}
    missing_ids = {str(selected["trial_id"]) for selected in selections(summary).values()
                   if selected is not None} - observed_ids
    if missing_ids:
        warnings.append(f"Missing trial evidence in {path.parent / 'events.jsonl'} for frozen selections: "
                        + ", ".join(sorted(missing_ids)) + "; outcomes remain unknown.")
    tests_path = path.parent / "test-results.json"
    tests = read_object(tests_path, warnings).get("selections", {}) if tests_path.exists() else {}
    for name, selection in selections(summary).items():
        stored = cache.get((selection or {}).get("artifact_hash"))
        if stored is not None:
            tests[name] = {**stored, "status": "uncertain"} if stored.get("status") == "in_progress" else stored
    postrun_path = path.parent / "postrun.json"
    return RunArtifacts(path.parent, summary, events, tests,
                        read_object(postrun_path, warnings) if postrun_path.exists() else {},
                        data_fingerprint(summary, events), (path.parent / "events.jsonl").exists())


def load_report(root: Path) -> ReportArtifacts:
    root = Path(root)
    warnings: list[str] = []
    cache_path = root / "evaluation" / "test-evaluation-cache.json"
    shared_test_cache = (read_object(cache_path, warnings).get("artifacts", {})
                         if cache_path.exists() else {})
    paths = ([root / "summary.json"] if (root / "summary.json").exists() else [])
    if (root / "runs").exists():
        paths.extend(sorted((root / "runs").rglob("summary.json")))
    manifest_path = root / "suite.json"
    manifest = read_object(manifest_path, warnings) if manifest_path.exists() else {}
    records = {path: read_object(path, warnings) for path in dict.fromkeys(paths)}
    metadata_fields = ("objective", "problem", "problem_hash", "target_definitions", "data_fingerprint")
    metadata = {key: manifest[key] for key in metadata_fields if key in manifest}
    if "objective" not in metadata:
        inferred = next(({key: item[key] for key in metadata_fields if key in item}
                         for item in records.values() if "objective" in item), {})
        metadata = {**inferred, **metadata}
    if "data_fingerprint" not in manifest and manifest_path.exists():
        metadata["data_fingerprint"] = ((manifest.get("provenance") or {}).get("data_manifest") or {}).get("data_fingerprint")
    runs = []
    if manifest_path.exists():
        config = manifest.get("config") or {}
        planned = manifest.get("schedule", [])
        planned_paths = set()
        for entry in planned:
            path = root / "runs" / entry["run_id"] / "summary.json"
            planned_paths.add(path)
            if path in records:
                summary = records[path]
            else:
                interrupted = (path.parent / "events.jsonl").exists()
                warnings.append(f"Incomplete suite: {entry['run_id']} "
                                + ("needs recovery after interruption." if interrupted else "has not started."))
                run_config = {**config, "condition": entry["condition"], "repeat": entry["repeat"]}
                if 'supervisor_strategy' in entry:
                    run_config['supervisor_strategy'] = entry['supervisor_strategy']
                if 'lesson_memory' in entry:
                    run_config['lesson_memory'] = entry['lesson_memory']
                if type(config.get("training_seed")) is int:
                    run_config["training_seed"] = config["training_seed"] + entry["repeat"]
                summary = {**metadata, "run_id": entry["run_id"], "condition": entry["condition"],
                           "repeat": entry["repeat"], "config": run_config,
                           "allowance_seconds": config.get("allowance_seconds"),
                           "stop_reason": "interrupted_unrecovered" if interrupted else "not_started"}
            runs.append(load_run(path, summary, shared_test_cache, warnings))
        if set(paths) - planned_paths:
            warnings.append("Unscheduled run directories were excluded from the frozen suite comparison.")
    else:
        runs = [load_run(path, summary, shared_test_cache, warnings) for path, summary in records.items()]
    postrun_path = root / "postrun.json"
    postrun = read_object(postrun_path, warnings) if postrun_path.exists() else {}
    return ReportArtifacts(runs, metadata, warnings, postrun, manifest_path.exists())
