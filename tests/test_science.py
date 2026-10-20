"""Scientific boundary tests: data isolation, deterministic models, durable results."""
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


def test_science_evaluator_is_available():
    assert importlib.util.find_spec("study.science") is not None, "scientific evaluator is missing"


def science():
    from study import science as module
    return module


@pytest.fixture
def prepared(tmp_path):
    data = tmp_path / "data"
    science().prepare_dataset(data, synthetic=True, seed=17)
    return data


def test_split_is_reproducible_disjoint_and_stratified(tmp_path):
    mod = science()
    a, b = tmp_path / "a", tmp_path / "b"
    ma = mod.prepare_dataset(a, synthetic=True, seed=7)
    mb = mod.prepare_dataset(b, synthetic=True, seed=7)
    assert ma == mb
    partitions = [np.load(a / f"{name}.npz") for name in ("train", "validation", "test")]
    assert [len(p["y"]) for p in partitions] == [600, 200, 200]
    assert [int(p["y"].sum()) for p in partitions] == [300, 100, 100]
    ids = [set(p["row_ids"].tolist()) for p in partitions]
    assert len(set.union(*ids)) == 1000
    assert not ids[0] & ids[1] and not ids[0] & ids[2] and not ids[1] & ids[2]
    for name in ("train", "validation", "test"):
        assert (a / f"{name}.npz").read_bytes() == (b / f"{name}.npz").read_bytes()
    assert mod.prepare_dataset(a, synthetic=True, seed=7) == ma
    with pytest.raises(ValueError, match="immutable"):
        mod.prepare_dataset(a, synthetic=True, seed=8)


def test_local_magic_parser_and_agent_info_hide_test(tmp_path):
    csv = tmp_path / "magic.csv"
    csv.write_text("\n".join(",".join([str(i + j / 10) for j in range(10)] + ["g" if i % 2 else "h"]) for i in range(100)))
    target = tmp_path / "data"
    manifest = science().prepare_dataset(target, csv_path=csv, seed=42)
    assert manifest["dataset"] == "MAGIC"
    assert len(manifest["feature_names"]) == 10
    info = science().project_info(target)
    assert "test" not in json.dumps(info).lower()
    assert info["counts"] == {"train": 60, "validation": 20}
    assert info["positive_class"] == "gamma (g)"
    with pytest.raises(ValueError):
        science().prepare_dataset(tmp_path / "missing")
    bad = tmp_path / "bad.csv"
    bad.write_text("1,2,evil")
    with pytest.raises(ValueError):
        science().prepare_dataset(tmp_path / "bad", csv_path=bad)


@pytest.mark.parametrize("config", [
    {"model": "shell", "preprocessing": "none", "params": {}},
    {"model": "logistic", "preprocessing": "none", "params": {"n_jobs": -1}},
    {"model": "logistic", "preprocessing": "none", "params": {"C": float("nan")}},
    {"model": "random_forest", "preprocessing": "none", "params": {"n_estimators": 100000}},
    {"model": "logistic", "preprocessing": "none", "params": {}, "code": "print(1)"},
    {"model": "logistic", "preprocessing": "none", "params": {"max_iter": True}},
])
def test_schema_rejects_unbounded_or_unsafe_config(config):
    with pytest.raises(ValueError):
        science().validate_config(config)


@pytest.mark.parametrize("model", ["logistic", "random_forest", "histogram_gradient_boosting"])
def test_pipeline_seed_and_train_only_preprocessing(model, monkeypatch):
    monkeypatch.setenv("LOKY_MAX_CPU_COUNT", "1")
    mod = science()
    config = {"model": model, "preprocessing": "standard", "params": {}}
    pipeline = mod.build_pipeline(config, seed=19)
    X = np.array([[0., 0.], [2., 4.], [4., 2.], [6., 6.]])
    y = np.array([0, 0, 1, 1])
    X, y = np.tile(X, (10, 1)), np.tile(y, 10)
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        pipeline.fit(X, y)
    assert pipeline.named_steps["scale"].mean_.tolist() == [3., 3.]
    pipeline.predict_proba(np.array([[1000., 1000.]]))
    assert pipeline.named_steps["scale"].mean_.tolist() == [3., 3.]
    classifier = pipeline.named_steps["classifier"]
    assert classifier.random_state == 19
    if model == "random_forest":
        assert classifier.n_jobs == 1


def test_trial_completes_without_test_partition_and_saves_verified_artifact(prepared, tmp_path):
    (prepared / "test.npz").unlink()
    result = asyncio.run(science().run_trial(prepared, tmp_path / "trial", {"model": "logistic", "preprocessing": "standard", "params": {}}, seed=5, timeout=20))
    assert result["status"] == "completed", result
    assert .5 < result["validation_auc"] <= 1
    artifact = Path(result["artifact"])
    assert artifact.is_file()
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == result["artifact_hash"]
    assert json.loads((tmp_path / "trial" / "result.json").read_text()) == result


def test_failed_and_timeout_trials_do_not_supply_artifacts(prepared, tmp_path):
    bad = asyncio.run(science().run_trial(prepared, tmp_path / "bad", {"model": "oops"}, seed=1, timeout=10))
    assert bad["status"] == "failed"
    result = asyncio.run(science().run_trial(prepared, tmp_path / "slow", {"model": "random_forest", "preprocessing": "none", "params": {"n_estimators": 300}}, seed=1, timeout=.001))
    assert result["status"] == "timeout"
    assert "artifact" not in result
    assert not (tmp_path / "slow" / "model.joblib").exists()


def test_test_evaluation_deduplicates_and_survives_reinvocation(prepared, tmp_path, monkeypatch):
    mod = science()
    trial = asyncio.run(mod.run_trial(prepared, tmp_path / "trial", {"model": "logistic", "preprocessing": "standard", "params": {}}, seed=5, timeout=20))
    selected = {"best": trial, "milestone": trial}
    first = mod.evaluate_selected(prepared, tmp_path / "run", selected)
    assert first["best"]["status"] == "completed"
    assert .5 < first["best"]["test_auc"] <= 1
    assert first["best"] == first["milestone"]
    (prepared / "test.npz").unlink()
    assert mod.evaluate_selected(prepared, tmp_path / "run", selected) == first


def test_reserved_evaluation_is_not_repeated_after_crash(prepared, tmp_path):
    mod = science()
    run = tmp_path / "run"
    run.mkdir()
    cache = {"version": 1, "artifacts": {"abc": {"artifact_hash": "abc", "status": "in_progress"}}}
    (run / "test-evaluation-cache.json").write_text(json.dumps(cache))
    result = mod.evaluate_selected(prepared, run, {"best": {"artifact_hash": "abc", "artifact": "/does/not/exist"}})
    assert result["best"]["status"] == "uncertain"


def test_evaluation_rejects_modified_artifact(prepared, tmp_path):
    mod = science()
    trial = asyncio.run(mod.run_trial(prepared, tmp_path / "trial", {"model": "logistic", "preprocessing": "standard", "params": {}}, seed=5, timeout=20))
    Path(trial["artifact"]).write_bytes(b"changed")
    result = mod.evaluate_selected(prepared, tmp_path / "run", {"best": trial})
    assert result["best"]["status"] == "failed"
    assert "hash" in result["best"]["error"]


def test_fixed_reference_is_async_and_returns_frozen_configuration(prepared, tmp_path):
    result = asyncio.run(science().fixed_reference(prepared, tmp_path / "reference", seed=9, timeout=20))
    assert result["status"] == "completed"
    assert result["config"]["model"] == "histogram_gradient_boosting"
    assert result["seed"] == 9


def test_worker_environment_excludes_secrets_and_receives_no_test_path(prepared, tmp_path, monkeypatch):
    mod = science()
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-do-not-inherit")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "also-secret")
    real_spawn = asyncio.create_subprocess_exec
    captured = {}

    async def capture_spawn(*args, **kwargs):
        captured.update(kwargs)
        process = await real_spawn(*args, **kwargs)
        real_communicate = process.communicate

        async def capture_request(request):
            captured["request"] = json.loads(request)
            return await real_communicate(request)

        process.communicate = capture_request
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", capture_spawn)
    result = asyncio.run(mod.run_trial(prepared, tmp_path / "trial", {"model": "logistic", "preprocessing": "standard", "params": {}}, seed=2, timeout=20))
    assert result["status"] == "completed"
    assert "OPENROUTER_API_KEY" not in captured["env"]
    assert "AWS_SECRET_ACCESS_KEY" not in captured["env"]
    assert captured["env"]["OMP_NUM_THREADS"] == "1"
    assert captured["env"]["LOKY_MAX_CPU_COUNT"] == "1"
    assert captured["start_new_session"] is True
    assert set(captured["request"]) == {"train_path", "validation_path", "artifact_path", "config", "seed", "metadata", "cores"}
    assert captured["request"]["train_path"] == str(prepared / "train.npz")
    assert captured["request"]["validation_path"] == str(prepared / "validation.npz")


def test_parent_cancellation_reaps_trial_process_group(prepared, tmp_path, monkeypatch):
    import os
    mod = science()
    real_spawn = asyncio.create_subprocess_exec
    processes = []

    async def exercise():
        spawned = asyncio.Event()

        async def capture_spawn(*args, **kwargs):
            process = await real_spawn(*args, **kwargs)
            processes.append(process)
            spawned.set()
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", capture_spawn)
        task = asyncio.create_task(mod.run_trial(prepared, tmp_path / "trial", {"model": "random_forest", "preprocessing": "none", "params": {"n_estimators": 300}}, seed=2, timeout=20))
        await spawned.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    assert processes[0].returncode is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(processes[0].pid, 0)
    assert not (tmp_path / "trial" / "model.joblib").exists()


def test_cancellation_during_spawn_still_reaps_child(prepared, tmp_path, monkeypatch):
    mod = science()
    real_spawn = asyncio.create_subprocess_exec
    processes = []

    async def exercise():
        spawned = asyncio.Event()

        async def delayed_spawn(*args, **kwargs):
            process = await real_spawn(*args, **kwargs)
            processes.append(process)
            spawned.set()
            await asyncio.sleep(.05)
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed_spawn)
        task = asyncio.create_task(mod.run_trial(prepared, tmp_path / "trial", {"model": "logistic", "preprocessing": "none", "params": {}}, seed=2, timeout=20))
        await spawned.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        try:
            assert processes[0].returncode is not None, "spawn cancellation leaked the child"
        finally:
            if processes[0].returncode is None:
                processes[0].kill()
                await processes[0].wait()

    asyncio.run(exercise())
