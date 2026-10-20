import asyncio
from datetime import datetime, timedelta, timezone
import json

import pytest

from study.config import CONDITIONS, StudyConfig
from study.suite import run_suite


def test_suite_requires_full_equal_allowances_and_reserve_before_any_call(tmp_path):
    called = []
    async def runner(*args, **kwargs):
        called.append(True)
    with pytest.raises(ValueError, match="window"):
        asyncio.run(run_suite(StudyConfig(allowance_seconds=60), tmp_path, tmp_path / "suite",
            repeats=2, deadline=datetime.now(timezone.utc) + timedelta(seconds=100),
            reserve_seconds=20, model_factory=lambda config: None, runner=runner))
    assert called == []


def test_suite_interleaves_all_conditions_with_matched_seeds_and_frozen_manifest(tmp_path):
    configs = []
    async def runner(config, data_dir, run_dir, model):
        configs.append(config)
        run_dir.mkdir(parents=True)
        return {"stop_reason": "trial_cap"}
    directory = tmp_path / "suite"
    asyncio.run(run_suite(StudyConfig(allowance_seconds=1), tmp_path, directory,
        repeats=2, deadline=datetime.now(timezone.utc) + timedelta(seconds=60),
        reserve_seconds=5, model_factory=lambda config: None, runner=runner))
    assert len(configs) == 10
    for repeat in range(2):
        group = [c for c in configs if c.repeat == repeat]
        assert {c.condition for c in group} == set(CONDITIONS)
        assert {c.training_seed for c in group} == {42 + repeat}
        assert {c.allowance_seconds for c in group} == {1}
    manifest = json.loads((directory / "suite.json").read_text())
    assert len(manifest["schedule"]) == 10
    assert manifest["reserve_seconds"] == 5


def test_accounting_does_not_double_count_cached_or_reasoning_tokens():
    from study.events import Accounting
    accounting = Accounting()
    accounting.add({"prompt_tokens": 100, "completion_tokens": 20, "cost": .2,
        "prompt_tokens_details": {"cached_tokens": 50},
        "completion_tokens_details": {"reasoning_tokens": 10}})
    assert accounting.input_tokens + accounting.output_tokens == 120
    assert accounting.cached_tokens == 50
    assert accounting.reasoning_tokens == 10
    accounting.add(None)
    assert accounting.known_cost == .2
    assert not accounting.cost_complete and not accounting.token_usage_complete


def test_invalid_problem_fails_before_model_factory_or_suite_creation(tmp_path):
    calls = []
    directory = tmp_path / "suite"
    with pytest.raises(ValueError):
        asyncio.run(run_suite(StudyConfig(allowance_seconds=1), tmp_path, directory,
            repeats=1, deadline=datetime.now(timezone.utc) + timedelta(seconds=60),
            reserve_seconds=5, model_factory=lambda config: calls.append(config),
            problem={"schema_version": 999}))
    assert calls == []
    assert not directory.exists()


@pytest.fixture
def prepared_accuracy_problem(tmp_path):
    from study.problem import ProblemSpec, legacy_problem
    from study.science import prepare_dataset
    value = legacy_problem().to_dict()
    value.update(id="custom-accuracy", brief="Compare classifiers by accuracy.")
    value["dataset"]["n_samples"] = 60
    value["evaluation"]["objective"] = {"metric": "accuracy", "direction": "maximize"}
    value["targets"] = [{"name": "acceptable", "value": .7}]
    problem = ProblemSpec.from_dict(value)
    data = tmp_path / "data"
    prepare_dataset(data, problem=problem)
    return data, problem


@pytest.mark.parametrize("tamper", ["profile", "partition"])
def test_suite_refuses_changed_frozen_science_before_factory(tmp_path, prepared_accuracy_problem, tamper):
    from study.problem import ProblemSpec
    data, problem = prepared_accuracy_problem
    if tamper == "profile":
        value = problem.to_dict()
        value["targets"][0]["value"] = .8
        problem = ProblemSpec.from_dict(value)
    else:
        (data / "train.npz").chmod(0o644)
        (data / "train.npz").write_bytes(b"changed prepared data")
    calls = []
    with pytest.raises(ValueError, match="frozen|differs|fingerprint"):
        asyncio.run(run_suite(StudyConfig(allowance_seconds=1), data, tmp_path / "suite",
            repeats=1, deadline=datetime.now(timezone.utc) + timedelta(seconds=60),
            reserve_seconds=5, model_factory=lambda config: calls.append(config), problem=problem))
    assert calls == []
    assert not (tmp_path / "suite").exists()


def test_suite_freezes_and_passes_one_resolved_problem(tmp_path, prepared_accuracy_problem):
    data, problem = prepared_accuracy_problem
    observed = []
    async def runner(config, data_dir, run_dir, model, *, problem):
        observed.append(problem.fingerprint)
        run_dir.mkdir(parents=True)
        return {"stop_reason": "trial_cap"}
    directory = tmp_path / "suite"
    asyncio.run(run_suite(StudyConfig(allowance_seconds=1), data, directory,
        repeats=1, deadline=datetime.now(timezone.utc) + timedelta(seconds=60),
        reserve_seconds=5, model_factory=lambda config: None, runner=runner))
    assert observed == [problem.fingerprint] * len(CONDITIONS)
    manifest = json.loads((directory / "suite.json").read_text())
    assert manifest["problem"] == problem.to_dict()
    assert manifest["problem_hash"] == problem.fingerprint
    assert manifest["target_definitions"] == problem.targets
    assert manifest["data_fingerprint"] == json.loads((data / "manifest.json").read_text())["data_fingerprint"]



def test_suite_unstarted_summary_preserves_prepared_fingerprint(tmp_path, prepared_accuracy_problem, monkeypatch):
    import study.suite as suite
    data, problem = prepared_accuracy_problem
    fingerprint = json.loads((data / "manifest.json").read_text())["data_fingerprint"]
    initial = datetime.now(timezone.utc)
    current = [initial]
    class Clock:
        @staticmethod
        def now(tz):
            return current[0]
    monkeypatch.setattr(suite, "datetime", Clock)
    async def runner(config, data_dir, run_dir, model, *, problem):
        current[0] = initial + timedelta(seconds=65)
        run_dir.mkdir(parents=True)
        return {"stop_reason": "trial_cap"}
    directory = tmp_path / "suite"
    summaries = asyncio.run(run_suite(StudyConfig(allowance_seconds=1), data, directory,
        repeats=1, deadline=initial + timedelta(seconds=60), reserve_seconds=5,
        model_factory=lambda config: None, runner=runner))
    assert len(summaries) == len(CONDITIONS)
    assert all(summary["data_fingerprint"] == fingerprint for summary in summaries[1:])
