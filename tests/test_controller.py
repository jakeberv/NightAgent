import asyncio
import json

import pytest

from study.config import StudyConfig
from study.controller import run_one, recover_run


class ScriptedModel:
    """External model boundary only; exercise the real controller and journal."""
    def __init__(self):
        self.roles = []
        self.tools = []

    async def complete(self, messages, tools, *, timeout):
        role = messages[0]["content"].split("\n", 1)[0]
        self.roles.append(role)
        self.tools.append((role, [t["function"]["name"] for t in tools]))
        if role == "ROLE: researcher":
            message = {"role": "assistant", "content": "Test a bounded classifier.",
                       "tool_calls": [{"id": f"call-{len(self.roles)}", "type": "function",
                                       "function": {"name": "run_analysis", "arguments": json.dumps(
                                           {"model": "logistic", "preprocessing": "standard", "params": {}})}}]}
        else:
            message = {"role": "assistant", "content": "Compare capacity; retain a controlled comparison."}
        return {"message": message, "usage": {"prompt_tokens": 10, "completion_tokens": 3,
                 "cost": 0.001}, "id": str(len(self.roles)), "provider": "fake", "model": "fake", "raw": {}}


async def trial(data_dir, trial_dir, config, *, seed, timeout):
    return {"status": "completed", "validation_auc": .96, "artifact": "fake.joblib",
            "artifact_hash": str(trial_dir), "elapsed_seconds": .01}


@pytest.mark.parametrize("condition,reviews,reflections", [
    ("researcher_alone", 0, 0),
    ("frequent", 6, 0),
    ("periodic", 2, 0),
    ("periodic_reflection", 2, 6),
    ("periodic_reflection_literature", 2, 6),
])
def test_exact_cadence_continues_after_threshold_and_skips_terminal_review(tmp_path, condition, reviews, reflections):
    model = ScriptedModel()
    config = StudyConfig(condition=condition, trial_cap=7, allowance_seconds=60)
    summary = asyncio.run(run_one(config, tmp_path / "data", tmp_path / "run", model,
                                 trial_runner=trial, project={"features": 10}))
    assert model.roles.count("ROLE: researcher") == 7
    assert model.roles.count("ROLE: supervisor") == reviews
    assert model.roles.count("ROLE: reflection") == reflections
    assert summary["stop_reason"] == "trial_cap"
    assert summary["best"]["trial_id"] == 1  # earliest wins ties
    assert summary["milestone"]["trial_id"] == 1
    assert summary["stretch"]["trial_id"] == 1
    for role, names in model.tools:
        assert ("run_analysis" in names) == (role == "ROLE: researcher")
        assert ("literature_search" in names) == (
            role == "ROLE: supervisor" and condition == "periodic_reflection_literature")
    if reflections:
        assert model.roles[5:8] == ["ROLE: supervisor", "ROLE: reflection", "ROLE: researcher"]


def test_failed_trials_count_towards_review_cadence(tmp_path):
    async def failed(*args, **kwargs):
        return {"status": "failed", "error": "fit failed", "elapsed_seconds": 0}
    model = ScriptedModel()
    result = asyncio.run(run_one(StudyConfig(condition="periodic", trial_cap=4),
        tmp_path, tmp_path / "run", model, trial_runner=failed, project={}))
    assert model.roles == ["ROLE: researcher"] * 3 + ["ROLE: supervisor", "ROLE: researcher"]
    assert result["trials"] == 4 and result["best"] is None


def test_late_trial_is_cancelled_and_never_selected(tmp_path):
    cancelled = []
    async def slow(*args, **kwargs):
        try:
            await asyncio.sleep(1)
        finally:
            cancelled.append(True)
    result = asyncio.run(run_one(StudyConfig(allowance_seconds=.04), tmp_path,
        tmp_path / "run", ScriptedModel(), trial_runner=slow, project={}))
    assert cancelled == [True]
    assert result["best"] is None
    assert result["stop_reason"] == "deadline"


def test_unknown_cost_is_not_zero_and_stops_by_default(tmp_path):
    class Unknown(ScriptedModel):
        async def complete(self, *args, **kwargs):
            response = await super().complete(*args, **kwargs)
            response["usage"].pop("cost")
            return response
    result = asyncio.run(run_one(StudyConfig(), tmp_path, tmp_path / "run", Unknown(),
                                trial_runner=trial, project={}))
    assert result["accounting"]["cost_complete"] is False
    assert result["stop_reason"] == "unknown_cost"
    assert result["trials"] == 0


def test_restart_never_renews_allowance_or_runs_model(tmp_path):
    model = ScriptedModel()
    run_dir = tmp_path / "run"
    first = asyncio.run(run_one(StudyConfig(trial_cap=1), tmp_path, run_dir, model,
                               trial_runner=trial, project={}))
    with pytest.raises(FileExistsError):
        asyncio.run(run_one(StudyConfig(trial_cap=1), tmp_path, run_dir, model,
                           trial_runner=trial, project={}))
    assert len(model.roles) == 1
    assert recover_run(run_dir) == first


def test_interrupted_journal_retains_valid_trial_and_usage(tmp_path):
    run_dir = tmp_path / "run"
    asyncio.run(run_one(StudyConfig(trial_cap=1), tmp_path, run_dir, ScriptedModel(),
                       trial_runner=trial, project={}))
    (run_dir / "summary.json").unlink()
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    (run_dir / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events
                                               if e["type"] != "run_stopped"))
    recovered = recover_run(run_dir)
    assert recovered["stop_reason"] == "interrupted"
    assert recovered["best"]["validation_auc"] == .96
    assert recovered["accounting"]["known_cost"] == .001


def test_invalid_config_rejects_unfair_or_nonfinite_budgets():
    for kwargs in ({"allowance_seconds": float("nan")}, {"trial_cap": 0},
                   {"condition": "sixth"}, {"milestone": .98, "stretch": .95}):
        with pytest.raises(ValueError):
            StudyConfig(**kwargs)


def test_cancelled_model_call_has_unknown_accounting(tmp_path):
    class Hanging:
        async def complete(self, *args, **kwargs):
            await asyncio.sleep(10)
    async def exercise():
        task = asyncio.create_task(run_one(StudyConfig(), tmp_path, tmp_path / "run",
            Hanging(), trial_runner=trial, project={}))
        await asyncio.sleep(.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(exercise())
    summary = json.loads((tmp_path / "run" / "summary.json").read_text())
    assert summary["stop_reason"] == "interrupted"
    assert summary["accounting"]["cost_complete"] is False
    assert summary["accounting"]["calls"] == 1


def test_retry_includes_failed_call_usage(tmp_path):
    class Transient(ScriptedModel):
        async def complete(self, *args, **kwargs):
            if not hasattr(self, "failed"):
                self.failed = True
                error = RuntimeError("transient failure")
                error.details = {"usage": {"prompt_tokens": 5, "completion_tokens": 0, "cost": .002}}
                raise error
            return await super().complete(*args, **kwargs)
    result = asyncio.run(run_one(StudyConfig(trial_cap=1), tmp_path, tmp_path / "run",
        Transient(), trial_runner=trial, project={}))
    assert result["accounting"]["calls"] == 2
    assert result["accounting"]["known_cost"] == .003
    assert result["accounting"]["input_tokens"] == 15


def test_literature_cap_limits_actual_io_and_keeps_unhelpful_evidence(tmp_path):
    class Searching(ScriptedModel):
        async def complete(self, messages, tools, *, timeout):
            response = await super().complete(messages, tools, timeout=timeout)
            if messages[0]["content"].startswith("ROLE: supervisor"):
                response["message"]["tool_calls"] = [{
                    "id": f"search-{i}", "type": "function", "function": {
                        "name": "literature_search", "arguments": '{"query":"tree capacity"}'}}
                    for i in range(5)]
            return response
    class Literature:
        queries = []
        async def search(self, query, *, timeout):
            self.queries.append(query)
            return {"query": query, "sources": [], "note": "No useful source"}
    literature = Literature()
    result = asyncio.run(run_one(StudyConfig(condition="periodic_reflection_literature", trial_cap=4,
        literature_calls_per_review=2), tmp_path, tmp_path / "run", Searching(),
        trial_runner=trial, project={}, literature=literature))
    assert result["trials"] == 4
    assert len(literature.queries) == 2
    journal = (tmp_path / "run" / "events.jsonl").read_text()
    assert "No useful source" in journal and "Per-review literature cap reached" in journal
