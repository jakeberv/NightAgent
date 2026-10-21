"""Offline integration checks for the administrator workflow."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from admin_demo.evidence import collect
from admin_demo.run import write_report, read_replay
from study.config import StudyConfig
from study.controller import run_one
from study.fake import FakeModel
from study.science import prepare_dataset, fixed_reference
from study.suite import provenance
from study.problem import ProblemSpec
from study.workshop_eval import run_evaluation


@pytest.fixture(scope="module")
def recording(tmp_path_factory):
    root = tmp_path_factory.mktemp("admin-recording")
    data = root / "data"
    problem = ProblemSpec.from_dict({
        "schema_version": 1, "id": "admin-test", "task": "tabular_classification",
        "brief": "Offline integration fixture", "dataset": {"format": "synthetic", "n_samples": 150, "n_features": 6},
        "evaluation": {"split": {"method": "stratified_holdout", "train": .6, "validation": .2, "test": .2, "seed": 42},
                       "objective": {"metric": "accuracy", "direction": "maximize"}, "additional_metrics": ["macro_f1"]},
        "targets": [{"name": "useful", "value": .8}],
        "search_space": {"preset": "tabular_classification_small", "models": ["logistic"]}})
    prepare_dataset(data, problem=problem)
    config = StudyConfig(condition="researcher_alone", model="offline-script", provider="offline",
                         trial_cap=7, allowance_seconds=300, dollar_cap=1,
                         lesson_memory=True, device="cpu", max_cores=1)

    async def run():
        await fixed_reference(data, root / "reference", seed=42, timeout=45)
        await run_one(config, data, root / "runs" / "researcher_alone",
                      FakeModel(options=[{"model": "logistic", "preprocessing": "standard",
                                          "params": {"C": c}} for c in range(1, 8)]),
                      provider_metadata={"runtime": provenance(data)})
    asyncio.run(run())
    assert run_evaluation(root / "engineering")["passed"]
    return root


@pytest.fixture
def attempt(recording, tmp_path):
    root = tmp_path / "attempt"
    shutil.copytree(recording, root)
    for path in root.rglob("*"):
        if path.suffix in (".json", ".jsonl"):
            path.write_text(path.read_text().replace(str(recording), str(root)))
    return root


def test_complete_loop_reports_measured_results_and_labels_scripted_provider(attempt):
    result = collect(attempt)
    assert result["passed"], result["audit"]
    assert result["source_kind"] == "scripted"
    assert len(result["trace"]) == 7
    assert result["memory"]["deliveries"] > 0
    assert result["reference"]["score"] > 0
    assert result["trace"][0]["tool"] == "run_analysis"
    assert result["trace"][1]["evidence"]


@pytest.mark.parametrize("mutation", ["artifact", "citation", "delivery", "unfinished", "engineering", "tool_arguments", "reference"])
def test_corrupt_or_incomplete_evidence_cannot_pass(attempt, mutation):
    run = attempt / "runs" / "researcher_alone"
    journal = run / "events.jsonl"
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    if mutation == "artifact":
        Path(next(e["result"]["artifact"] for e in events if e["type"] == "trial_finished")).write_bytes(b"changed")
    elif mutation == "citation":
        event = next(e for e in events if e["type"] == "decision_contract" and e["contract"]["evidence"])
        event["contract"]["evidence"][0]["value"] = -99
        start = next(e for e in events if e["type"] == "trial_started" and e["trial_id"] == event["trial_id"])
        start["intent"] = event["contract"]
    elif mutation == "delivery":
        for event in events:
            if event["type"] == "model_call_started":
                context = json.loads(event["messages"][1]["content"])
                context["lessons"] = []
                event["messages"][1]["content"] = json.dumps(context)
    elif mutation == "unfinished":
        events.pop()
    elif mutation == "tool_arguments":
        event = next(e for e in events if e["type"] == "decision")
        function = event["message"]["tool_calls"][0]["function"]
        args = json.loads(function["arguments"])
        args["params"]["C"] = 999
        function["arguments"] = json.dumps(args)
    elif mutation == "reference":
        ref = attempt / "reference" / "result.json"
        data = json.loads(ref.read_text())
        data["score"] = 1.0
        ref.write_text(json.dumps(data))
    else:
        (attempt / "engineering" / "results.json").write_text('{"passed": false, "cases": []}')
    journal.write_text("".join(json.dumps(e) + "\n" for e in events))
    assert not collect(attempt)["passed"]


def test_report_escapes_agent_text_and_replay_needs_no_repository(recording, tmp_path):
    result = collect(recording)
    result["trace"][0]["summary"] = "<script>alert('agent')</script>"
    write_report(result, tmp_path, replay=True)
    html = (tmp_path / "report.html").read_text()
    assert "&lt;script&gt;" in html and "<script>alert" not in html
    assert "SAVED REPLAY" in html and "SCRIPTED" in html
    # Copy only the entry point and its saved payload: replay must be stdlib-only.
    folder = tmp_path / "standalone"
    folder.mkdir()
    shutil.copy(Path(__file__).with_name("run.py"), folder / "run.py")
    (folder / "saved").mkdir()
    shutil.copy(tmp_path / "results.json", folder / "saved" / "results.json")
    completed = subprocess.run([sys.executable, "-I", str(folder / "run.py"), "--replay",
                                "--output", str(folder / "output")], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "SAVED REPLAY" in (folder / "output" / "report.html").read_text()


def test_replay_detects_accidental_changes(recording, tmp_path):
    write_report(collect(recording), tmp_path, replay=False)
    path = tmp_path / "results.json"
    envelope = json.loads(path.read_text())
    envelope["result"]["best_score"] = 1.0
    path.write_text(json.dumps(envelope))
    with pytest.raises(ValueError, match="checksum"):
        read_replay(path)


def test_missing_key_fails_without_a_live_run_or_silent_fallback(tmp_path):
    environment = dict(os.environ)
    environment.pop("OPENROUTER_API_KEY", None)
    empty_env = tmp_path / "empty.env"
    empty_env.write_text("")
    output = tmp_path / "output"
    completed = subprocess.run([sys.executable, str(Path(__file__).with_name("run.py")),
                                "--env-file", str(empty_env), "--output", str(output)],
                               env=environment, capture_output=True, text=True, cwd=tmp_path)
    assert completed.returncode == 1
    assert "API key" in completed.stderr
    assert not (output / "runs").exists() and not (output / "results.json").exists()


def test_existing_output_is_never_overwritten(tmp_path):
    marker = tmp_path / "results.json"
    marker.write_text("preserve this evidence")
    completed = subprocess.run([sys.executable, str(Path(__file__).with_name("run.py")),
                                "--replay", "--output", str(tmp_path)], capture_output=True)
    assert completed.returncode == 1
    assert marker.read_text() == "preserve this evidence"


@pytest.mark.parametrize("replacement", ["duplicate", "unrelated"])
def test_eight_passing_entries_must_be_the_eight_named_cases(attempt, replacement):
    path = attempt / "engineering" / "results.json"
    result = json.loads(path.read_text())
    result["cases"][0]["id"] = result["cases"][1]["id"] if replacement == "duplicate" else "unrelated-case"
    path.write_text(json.dumps(result))
    assert not collect(attempt)["passed"]
