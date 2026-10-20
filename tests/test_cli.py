import asyncio
import json

from study.__main__ import evaluate
from study.events import atomic_json
from study.science import prepare_dataset, run_trial
import pytest


@pytest.mark.parametrize("command", ["run", "suite", "suite-validation"])
@pytest.mark.parametrize("billing", ["known", "unknown"])
def test_live_cli_failure_exits_nonzero_and_preserves_results(tmp_path, monkeypatch, command, billing):
    import sys
    from datetime import datetime, timedelta, timezone
    from study.__main__ import main
    from study.provider import ProviderError
    data, output = tmp_path / "data", tmp_path / "output"
    prepare_dataset(data, synthetic=True)
    config = tmp_path / "config.json"
    # Exercise a provider failure, rather than the API-start deadline guard.
    config.write_text(json.dumps({"model_retries": 0, "allowance_seconds": 1,
                                  "model_start_buffer_seconds": 0}))
    class FailedProvider:
        async def describe(self):
            return {"offline": True}
        async def complete(self, *args, **kwargs):
            usage = {"cost": 0, "prompt_tokens": 0, "completion_tokens": 0} if billing == "known" else None
            raise ProviderError("Fixture provider failure", {"usage": usage})
        async def aclose(self):
            pass
    monkeypatch.setattr("study.__main__.live_model", lambda _: FailedProvider())
    validation_only = command == 'suite-validation'
    command = 'suite' if validation_only else command
    argv = ["study", command, "--config", str(config), "--data", str(data), "--output", str(output)]
    if validation_only:
        argv.append('--validation-only')
    if command == "suite":
        argv += ["--repeats", "1", "--reserve-seconds", "10", "--deadline",
                 (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exited:
        main()
    assert exited.value.code != 0
    summaries = [output / "summary.json"] if command == "run" else list((output / "runs").glob("*/summary.json"))
    assert len(summaries) == (1 if command == "run" else 5)
    assert all(json.loads(path.read_text())["stop_reason"] ==
               ("model_failure" if billing == "known" else "unknown_cost") for path in summaries)
    if command == "suite":
        assert (output / "report.html").exists()
        assert json.loads((output / "completion.json").read_text())["postrun"]["report"] == "completed"


@pytest.mark.parametrize("stop,best,failed", [
    ("deadline", {"score": .8}, False), ("trial_cap", {"score": .8}, False),
    ("dollar_cap", {"score": .8}, False), ("deadline", None, True),
    ("trial_cap", None, True), ("no_progress", {"score": .8}, True),
    ("failure", {"score": .8}, True), ("interrupted", {"score": .8}, True),
    ("not_started_study_deadline", None, True),
])
def test_run_outcome_distinguishes_expected_limits_from_failures(stop, best, failed):
    from study.__main__ import require_successful_runs
    summaries = [{"condition": "researcher_alone", "repeat": 0, "stop_reason": stop, "best": best}]
    if failed:
        with pytest.raises(RuntimeError):
            require_successful_runs(summaries)
    else:
        require_successful_runs(summaries)


def test_reference_timeout_cli_exits_nonzero(tmp_path, monkeypatch):
    import sys
    from study.__main__ import main
    data = tmp_path / "data"
    prepare_dataset(data, synthetic=True)
    monkeypatch.setattr(sys, "argv", ["study", "reference", "--data", str(data),
        "--output", str(tmp_path / "reference"), "--timeout", "0.000001"])
    with pytest.raises(SystemExit) as exited:
        main()
    assert exited.value.code != 0


def test_evaluate_cli_exits_nonzero_after_persisting_failed_scoring(tmp_path, monkeypatch):
    import sys
    from study.__main__ import main
    data, output = tmp_path / "data", tmp_path / "run"
    prepare_dataset(data, synthetic=True)
    output.mkdir()
    atomic_json(output / "summary.json", {"best": {
        "artifact": str(tmp_path / "missing.joblib"), "artifact_hash": "absent"}})
    monkeypatch.setattr(sys, "argv", ["study", "evaluate", "--data", str(data),
        "--output", str(output)])
    with pytest.raises(SystemExit) as exited:
        main()
    assert exited.value.code != 0
    result = json.loads((output / "test-results.json").read_text())
    assert result["selections"]["best"]["status"] == "failed"


@pytest.mark.parametrize("expired", [False, True])
def test_postrun_failure_is_reported_after_writing_completion(tmp_path, expired):
    from datetime import datetime, timedelta, timezone
    from study.__main__ import finish_before_deadline
    deadline = datetime.now(timezone.utc) + timedelta(seconds=-1 if expired else 30)
    with pytest.raises(RuntimeError, match="Postrun"):
        asyncio.run(finish_before_deadline(tmp_path / "missing-data", tmp_path, deadline))
    statuses = json.loads((tmp_path / "completion.json").read_text())["postrun"]
    assert set(statuses) == {"evaluate", "report"}
    assert statuses["evaluate"] == ("not_started_deadline" if expired else "failed")


@pytest.mark.parametrize("display", ["--quiet", "--verbose"])
def test_cli_reads_explicit_env_file_and_controls_display_without_losing_logs(
        tmp_path, monkeypatch, capsys, display):
    import os
    import sys
    from study.__main__ import main
    from study.fake import FakeModel
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    data, output = tmp_path / "data", tmp_path / "run"
    prepare_dataset(data, synthetic=True)
    config = tmp_path / "config.json"
    config.write_text('{"trial_cap":1,"allowance_seconds":30}')
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_API_KEY=fixture-secret\nLLM_BASE_URL=https://openrouter.ai/api/v1")
    class Offline(FakeModel):
        async def describe(self):
            return {"offline": True}
    def provider(config):
        assert os.environ["OPENROUTER_API_KEY"] == "fixture-secret"
        return Offline()
    monkeypatch.setattr("study.__main__.live_model", provider)
    monkeypatch.setattr(sys, "argv", ["study", "run", "--config", str(config), "--data", str(data),
        "--output", str(output), "--env-file", str(env_file), display])
    main()
    captured = capsys.readouterr()
    assert json.loads(captured.out)["trials"] == 1
    assert ("trial 1" in captured.err) == (display == "--verbose")
    assert "trial 1" in (output / "progress.log").read_text()
    assert (output / "events.jsonl").exists()
    for path in output.glob("*.json*"):
        assert "fixture-secret" not in path.read_text()
    assert "fixture-secret" not in captured.out + captured.err + (output / "progress.log").read_text()


def test_offline_model_can_execute_adapter_configuration_without_classifier_assumptions():
    from study.fake import FakeModel
    config = {"model": "ridge", "preprocessing": "standard", "params": {"alpha": 2}}
    response = asyncio.run(FakeModel(options=[config]).complete(
        [{"role": "system", "content": "ROLE: researcher\nMinimize RMSE"}], [], timeout=1))
    arguments = json.loads(response["message"]["tool_calls"][0]["function"]["arguments"])
    assert arguments.pop("intent")["supervisor_response"] == "not_applicable"
    assert arguments == config


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
    ("tabular_classification", "roc_auc_ovr_macro", "maximize", 0.0),
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
    from study.fake import bounded_options
    monkeypatch.setattr("study.__main__.live_model", lambda config: Offline(
        options=bounded_options(get_adapter(load_problem(profile)))))
    asyncio.run(dispatch(Namespace(command="run", problem=profile, config=config,
        data=data, output=run, condition=None)))
    summary = json.loads((run / "summary.json").read_text())
    assert summary["stop_reason"] == "trial_cap"
    assert summary["objective"] == {"metric": metric, "direction": direction}
    assert summary["best"]["score"] == summary["best"]["metrics"][metric]
    assert summary["target_selections"]["acceptable"] is not None
    assert "validation_auc" not in summary["best"]
    assert (run / "report.html").exists()
    assert (run / "figures" / "workflow.svg").exists()
    assert not (run / "test-results.json").exists()
    asyncio.run(dispatch(Namespace(command="evaluate", output=run, data=data)))
    report = build_report_data(run)
    assert report["runs"][0]["best_test_score"] is not None
    assert report["runs"][0]["targets"]["acceptable"]["reached"]


def test_failed_pilot_still_generates_report_without_scoring_test_data(tmp_path, monkeypatch):
    from argparse import Namespace
    from study.__main__ import dispatch
    data, run = tmp_path / 'data', tmp_path / 'run'
    prepare_dataset(data, synthetic=True)
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'allowance_seconds': 10, 'trial_cap': 1}))
    class Unavailable:
        async def describe(self):
            return {'offline': True}
        async def complete(self, *args, **kwargs):
            raise RuntimeError('simulated provider failure')
        async def aclose(self):
            pass
    monkeypatch.setattr('study.__main__.live_model', lambda _: Unavailable())
    with pytest.raises(RuntimeError, match='Search failed'):
        asyncio.run(dispatch(Namespace(command='run', config=config, data=data,
            output=run, condition=None, quiet=True)))
    assert (run / 'report.html').exists()
    assert json.loads((run / 'report-accounting.json').read_text())['api_calls'] == 0
    assert not (run / 'test-results.json').exists()


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


def test_cli_enables_run_local_memory_and_freezes_treatment(tmp_path, monkeypatch, capsys):
    import sys
    from study.__main__ import main
    from study.fake import FakeModel
    data, output = tmp_path / 'data', tmp_path / 'run'
    prepare_dataset(data, synthetic=True)
    config = tmp_path / 'config.json'
    config.write_text('{"trial_cap":2,"allowance_seconds":30}')
    class Offline(FakeModel):
        async def describe(self):
            return {'offline': True}
    monkeypatch.setattr('study.__main__.live_model', lambda config: Offline())
    monkeypatch.setattr(sys, 'argv', ['study', 'run', '--config', str(config), '--data', str(data),
        '--output', str(output), '--lesson-memory', '--quiet'])
    main()
    summary = json.loads((output / 'summary.json').read_text())
    assert summary['config']['lesson_memory'] is True
    assert summary['config']['decision_protocol'] == 'structured_v1'
    assert summary['lessons']
    assert (output / 'lessons.json').exists()
    assert not (output / 'test-results.json').exists()
def test_validation_only_suite_runs_all_strategies_without_heldout_scoring(tmp_path, monkeypatch):
    import sys
    from datetime import datetime, timedelta, timezone
    from study.__main__ import main
    from study.config import CONDITIONS
    from study.fake import FakeModel
    data, output = tmp_path / 'data', tmp_path / 'suite'
    prepare_dataset(data, synthetic=True)
    config = tmp_path / 'config.json'
    config.write_text('{"trial_cap":1,"allowance_seconds":10}')
    class Offline(FakeModel):
        async def describe(self):
            return {'offline': True}
    monkeypatch.setattr('study.__main__.live_model', lambda config: Offline())
    monkeypatch.setattr(sys, 'argv', ['study', 'suite', '--config', str(config),
        '--data', str(data), '--output', str(output), '--repeats', '1', '--max-cores', '2',
        '--reserve-seconds', '5', '--deadline',
        (datetime.now(timezone.utc) + timedelta(seconds=90)).isoformat(),
        '--validation-only', '--quiet'])
    main()
    summaries = [json.loads(p.read_text()) for p in output.glob('runs/*/summary.json')]
    assert {s['condition'] for s in summaries} == set(CONDITIONS)
    assert all(s['trials'] == 1 and s['best'] for s in summaries)
    assert (output / 'report.html').is_file()
    assert not (output / 'evaluation').exists()
    assert not list(output.glob('runs/*/test-results.json'))
    assert json.loads((output / 'completion.json').read_text())['postrun'] == {
        'evaluate': 'skipped_validation_only', 'report': 'completed'}
    assert json.loads((output / 'suite.json').read_text())['postrun_policy'] == 'validation_only'
