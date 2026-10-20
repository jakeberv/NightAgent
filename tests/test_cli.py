import asyncio
import json

from study.__main__ import evaluate
from study.events import atomic_json
from study.science import prepare_dataset, run_trial


def test_suite_evaluates_identical_selected_artifact_once_across_runs(tmp_path):
    data = tmp_path / "data"
    prepare_dataset(data, synthetic=True)
    artifact = asyncio.run(run_trial(data, tmp_path / "trial",
        {"model": "logistic", "preprocessing": "standard", "params": {}}, seed=42, timeout=15))
    assert artifact["status"] == "completed"
    suite = tmp_path / "suite"
    for name in ("a", "b"):
        run = suite / "runs" / name
        run.mkdir(parents=True)
        atomic_json(run / "summary.json", {"best": artifact, "milestone": artifact, "stretch": None})
    evaluate(data, suite)
    cache_path = suite / "evaluation" / "test-evaluation-cache.json"
    cache_before = cache_path.read_bytes()
    assert len(json.loads(cache_before)["artifacts"]) == 1
    a = json.loads((suite / "runs/a/test-results.json").read_text())
    b = json.loads((suite / "runs/b/test-results.json").read_text())
    assert a == b
    assert a["selections"]["best"]["status"] == "completed"
    # Re-running evaluation must use the durable cached score even if the
    # original artifact becomes unavailable, rather than scoring again.
    from pathlib import Path
    Path(artifact["artifact"]).unlink()
    evaluate(data, suite)
    assert cache_path.read_bytes() == cache_before
    assert json.loads((suite / "runs/a/test-results.json").read_text()) == a
