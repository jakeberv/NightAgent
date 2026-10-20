import asyncio
import json

from study.__main__ import evaluate
from study.events import atomic_json
from study.science import prepare_dataset, run_trial
import pytest


def test_offline_model_can_execute_adapter_configuration_without_classifier_assumptions():
    from study.fake import FakeModel
    config = {"model": "ridge", "preprocessing": "standard", "params": {"alpha": 2}}
    response = asyncio.run(FakeModel(options=[config]).complete(
        [{"role": "system", "content": "ROLE: researcher\nMinimize RMSE"}], [], timeout=1))
    assert json.loads(response["message"]["tool_calls"][0]["function"]["arguments"]) == config


def test_invalid_problem_is_rejected_before_model_or_network(tmp_path, monkeypatch):
    from study.__main__ import dispatch
    from argparse import Namespace
    problem = tmp_path / "bad.json"
    problem.write_text('{"task": "execute_any_python"}')
    config = tmp_path / "config.json"
    config.write_text("{}")
    calls = []
    monkeypatch.setattr("study.__main__.live_model", lambda _: calls.append(True))
    with pytest.raises(ValueError):
        asyncio.run(dispatch(Namespace(command="run", config=config, problem=problem,
            data=tmp_path / "missing", output=tmp_path / "run", condition=None)))
    assert calls == []


def test_problem_template_creation_refuses_to_overwrite(tmp_path):
    from study.__main__ import dispatch
    from argparse import Namespace
    destination = tmp_path / "problem.yaml"
    args = Namespace(command="init-problem", template="regression", output=destination)
    asyncio.run(dispatch(args))
    original = destination.read_bytes()
    assert b"tabular_regression" in original
    with pytest.raises(FileExistsError):
        asyncio.run(dispatch(args))
    assert destination.read_bytes() == original


def test_profile_seed_cannot_be_silently_overridden_by_legacy_flag(tmp_path):
    from argparse import Namespace
    from study.__main__ import dispatch
    with pytest.raises(ValueError, match="^Set split seed in the problem profile"):
        asyncio.run(dispatch(Namespace(command="prepare", problem=tmp_path / "unused.yaml",
                                      seed=7, output=tmp_path / "data")))


@pytest.mark.parametrize("task,metric,direction,target", [
    ("tabular_classification", "accuracy", "maximize", 0.0),
    ("tabular_regression", "rmse", "minimize", 1000000.0),
])
def test_profile_cli_prepare_run_evaluate_report_uses_configured_objective(
        tmp_path, monkeypatch, task, metric, direction, target):
    from argparse import Namespace
    from study.__main__ import dispatch
    from study.fake import FakeModel
    from study.problem import load_problem
    from study.tasks import get_adapter
    from study.report import build_report_data
    model_name = "logistic" if task == "tabular_classification" else "ridge"
    definition = {"schema_version": 1, "id": "custom-example", "task": task,
        "brief": "Compare bounded approaches on this independently specified problem.",
        "dataset": {"format": "synthetic", "n_samples": 150, "n_features": 4},
        "evaluation": {"split": {"train": .6, "validation": .2, "test": .2, "seed": 42},
                       "objective": {"metric": metric, "direction": direction}},
        "targets": [{"name": "acceptable", "value": target}],
        "search_space": {"preset": task + "_small", "models": [model_name]}}
    if task == "tabular_classification":
        definition["dataset"]["n_classes"] = 3
    profile = tmp_path / "problem.json"
    profile.write_text(json.dumps(definition))
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"trial_cap": 2, "allowance_seconds": 30}))
    data, run = tmp_path / "data", tmp_path / "run"
    asyncio.run(dispatch(Namespace(command="prepare", problem=profile, output=data)))

    class Offline(FakeModel):
        async def describe(self):
            return {"offline": True}
    monkeypatch.setattr("study.__main__.live_model", lambda config: Offline(
        options=[get_adapter(load_problem(profile)).reference_config]))
    asyncio.run(dispatch(Namespace(command="run", problem=profile, config=config,
        data=data, output=run, condition=None)))
    summary = json.loads((run / "summary.json").read_text())
    assert summary["stop_reason"] == "trial_cap"
    assert summary["objective"] == {"metric": metric, "direction": direction}
    assert summary["best"]["score"] == summary["best"]["metrics"][metric]
    assert summary["target_selections"]["acceptable"] is not None
    assert "validation_auc" not in summary["best"]
    asyncio.run(dispatch(Namespace(command="evaluate", output=run, data=data)))
    report = build_report_data(run)
    assert report["runs"][0]["best_test_score"] is not None
    assert report["runs"][0]["targets"]["acceptable"]["reached"]


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
