import asyncio
import json

import pytest

from study.config import StudyConfig
from study.controller import run_one
from study.recovery import recover_run


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
        from study.fake import scripted_contract
        context = json.loads(messages[1]["content"])
        contract = scripted_contract(role.removeprefix("ROLE: "), context)
        if role == "ROLE: researcher":
            arguments = json.loads(message["tool_calls"][0]["function"]["arguments"])
            arguments["intent"] = contract
            arguments["params"]["C"] = context["trials_attempted"] + 1
            message["tool_calls"][0]["function"]["arguments"] = json.dumps(arguments)
        else:
            message["content"] = json.dumps(contract)
        return {"message": message, "usage": {"prompt_tokens": 10, "completion_tokens": 3,
                 "cost": 0.001}, "id": str(len(self.roles)), "provider": "fake", "model": "fake", "raw": {}}


async def trial(data_dir, trial_dir, config, *, seed, timeout):
    return {"status": "completed", "validation_auc": .96, "metrics": {"roc_auc": .96}, "artifact": "fake.joblib",
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
    assert model.roles.count("ROLE: supervisor") == reviews + (condition != "researcher_alone")
    assert model.roles.count("ROLE: reflection") == reflections
    assert summary["stop_reason"] == "trial_cap"
    assert summary["best"]["trial_id"] == 1  # earliest wins ties
    assert summary["milestone"]["trial_id"] == 1
    assert summary["stretch"]["trial_id"] == 1
    for index, (role, names) in enumerate(model.tools):
        assert ("run_analysis" in names) == (role == "ROLE: researcher")
        assert ("literature_search" in names) == (
            role == "ROLE: supervisor" and condition == "periodic_reflection_literature" and index > 0)
    if reflections:
        assert model.roles[6:9] == ["ROLE: supervisor", "ROLE: reflection", "ROLE: researcher"]


def test_failed_trials_count_towards_review_cadence(tmp_path):
    async def failed(*args, **kwargs):
        return {"status": "failed", "error": "fit failed", "elapsed_seconds": 0}
    model = ScriptedModel()
    result = asyncio.run(run_one(StudyConfig(condition="periodic", trial_cap=4),
        tmp_path, tmp_path / "run", model, trial_runner=failed, project={}))
    assert model.roles == ["ROLE: supervisor"] + ["ROLE: researcher"] * 3 + ["ROLE: supervisor", "ROLE: researcher"]
    assert result["trials"] == 4 and result["best"] is None


def test_late_trial_is_cancelled_and_never_selected(tmp_path):
    cancelled = []
    async def slow(*args, **kwargs):
        try:
            await asyncio.sleep(1)
        finally:
            cancelled.append(True)
    result = asyncio.run(run_one(StudyConfig(allowance_seconds=.04, model_start_buffer_seconds=0), tmp_path,
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


@pytest.mark.parametrize("terminated", [False, True])
def test_recovery_only_tolerates_unterminated_corrupt_tail(tmp_path, terminated):
    run_dir = tmp_path / "run"
    asyncio.run(run_one(StudyConfig(trial_cap=1), tmp_path, run_dir, ScriptedModel(),
                       trial_runner=trial, project={}))
    summary_path = run_dir / "summary.json"
    summary_path.unlink()
    path = run_dir / "events.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    path.write_text("".join(json.dumps(e) + "\n" for e in events
                            if e["type"] != "run_stopped")
                    + '{"type":' + ("\n" if terminated else ""))
    if terminated:
        with pytest.raises(ValueError, match="Corrupt"):
            recover_run(run_dir)
        assert not summary_path.exists()
    else:
        recovered = recover_run(run_dir)
        assert recovered["best"]["validation_auc"] == .96
        assert recovered["accounting"]["known_cost"] == .001
        assert json.loads(summary_path.read_text()) == recovered


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
            if (messages[0]["content"].startswith("ROLE: supervisor") and len(messages) == 2
                    and json.loads(messages[1]["content"])["trials_attempted"] > 0):
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


@pytest.mark.parametrize("failure", ["forbidden", "timeout"])
def test_failed_literature_redirect_is_visible_to_supervisor_and_journal(tmp_path, failure):
    import httpx
    from study.literature import LiteratureClient
    observed = []
    class Reading(ScriptedModel):
        async def complete(self, messages, tools, *, timeout):
            response = await super().complete(messages, tools, timeout=timeout)
            if (messages[0]["content"].startswith("ROLE: supervisor")
                    and json.loads(messages[1]["content"])["trials_attempted"] > 0):
                if len(messages) == 2:
                    response["message"]["tool_calls"] = [{"id": "fetch", "type": "function",
                        "function": {"name": "literature_fetch",
                                     "arguments": '{"url":"https://doi.org/10.1234/example"}'}}]
                else:
                    observed.append(json.loads(messages[-1]["content"]))
            return response
    async def handler(request):
        if request.headers["host"] == "doi.org":
            return httpx.Response(302, headers={"location": "https://publisher.example/article"})
        if failure == "timeout":
            await asyncio.sleep(1)
        return httpx.Response(403)
    async def resolver(host, port):
        return ["93.184.216.34"]
    async def scenario():
        client = LiteratureClient(transport=httpx.MockTransport(handler), resolver=resolver)
        try:
            return await run_one(StudyConfig(condition="periodic_reflection_literature", trial_cap=4,
                                            literature_timeout_seconds=.05),
                tmp_path, tmp_path / "run", Reading(), trial_runner=trial, project={}, literature=client)
        finally:
            await client.aclose()
    summary = asyncio.run(scenario())
    assert summary["trials"] == 4
    assert ("TimeoutError" if failure == "timeout" else "403") in observed[0]["error"]
    assert observed[0]["evidence"]["final_url"] == "https://publisher.example/article"
    assert observed[0]["evidence"]["redirects"][0]["status"] == 302
    events = [json.loads(line) for line in (tmp_path / "run/events.jsonl").read_text().splitlines()]
    logged = next(e["result"] for e in events if e["type"] == "tool_call" and e["name"] == "literature_fetch")
    assert logged == observed[0]


def test_minimize_objective_selects_named_targets_and_earliest_ties():
    from types import SimpleNamespace
    from study.selection import select_result
    from study.events import Accounting
    problem = SimpleNamespace(objective={"metric": "rmse", "direction": "minimize"},
                              targets=[{"name": "useful", "value": 12.0},
                                       {"name": "excellent", "value": 8.0}])
    summary = {"best": None, "target_selections": {"useful": None, "excellent": None}}
    config = StudyConfig()
    for trial_id, score, elapsed in ((1, 15.0, 1), (2, 10.0, 2), (3, 7.0, 3), (4, 7.0, 4)):
        select_result(summary, {"status": "completed", "score": score, "metrics": {"rmse": score},
            "trial_id": trial_id, "elapsed_seconds": elapsed, "artifact": "fit.joblib",
            "artifact_hash": str(trial_id)}, Accounting(), config, problem=problem)
    assert summary["best"]["trial_id"] == 3
    assert summary["best"]["metrics"] == {"rmse": 7.0}
    assert summary["target_selections"]["useful"]["trial_id"] == 2
    assert summary["target_selections"]["excellent"]["trial_id"] == 3
    assert "validation_auc" not in summary["best"]


def test_generic_selection_rejects_failed_late_and_nonfinite_results():
    from types import SimpleNamespace
    from study.selection import select_result
    from study.events import Accounting
    problem = SimpleNamespace(objective={"metric": "r2", "direction": "maximize"},
                              targets=[{"name": "baseline", "value": -1.0}])
    summary = {"best": None, "target_selections": {"baseline": None}}
    config = StudyConfig(allowance_seconds=5)
    for score, status, elapsed in ((float("nan"), "completed", 1), (3, "failed", 1), (3, "completed", 6)):
        select_result(summary, {"status": status, "score": score, "metrics": {"r2": score},
            "trial_id": 1, "elapsed_seconds": elapsed, "artifact": "fit", "artifact_hash": "hash"},
            Accounting(), config, problem=problem)
    assert summary["best"] is None
    select_result(summary, {"status": "completed", "score": -0.5, "metrics": {"r2": -0.5},
        "trial_id": 2, "elapsed_seconds": 1, "artifact": "fit", "artifact_hash": "hash"},
        Accounting(), config, problem=problem)
    assert summary["best"]["score"] == -0.5
    assert summary["target_selections"]["baseline"]["trial_id"] == 2


@pytest.fixture
def regression_problem():
    from study.problem import ProblemSpec
    return ProblemSpec.from_dict({"schema_version": 1, "id": "test-regression", "task": "tabular_regression",
        "brief": "Predict the measured response with bounded regression experiments.",
        "dataset": {"format": "synthetic", "n_samples": 60, "n_features": 4},
        "evaluation": {"split": {"train": .6, "validation": .2, "test": .2},
                       "objective": {"metric": "rmse", "direction": "minimize"}},
        "targets": [{"name": "useful", "value": 12.0}, {"name": "excellent", "value": 8.0}],
        "search_space": {"preset": "tabular_regression_small", "models": ["ridge"]}})


def test_profile_controls_prompts_tools_and_frozen_recovery(tmp_path, regression_problem):
    from study.science import prepare_dataset
    from study.tasks import get_adapter
    data = tmp_path / "data"
    manifest = prepare_dataset(data, problem=regression_problem)
    observed = []

    from study.fake import scripted_contract

    class Regressor:
        async def complete(self, messages, tools, *, timeout):
            observed.append((messages, tools))
            return {"message": {"role": "assistant", "tool_calls": [{"id": "fit", "type": "function",
                "function": {"name": "run_analysis", "arguments": json.dumps(
                    {"model": "ridge", "preprocessing": "standard", "params": {"alpha": len(observed)},
                     "intent": scripted_contract(
                         "researcher", json.loads(messages[1]["content"]))})}}]},
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0}}

    scores = iter((14.0, 8.0, 11.0))
    async def regression_trial(*args, **kwargs):
        score = next(scores)
        return {"status": "completed", "metrics": {"rmse": score}, "score": score,
                "artifact": "fit.joblib", "artifact_hash": str(score)}

    directory = tmp_path / "run"
    result = asyncio.run(run_one(StudyConfig(trial_cap=3), data, directory, Regressor(),
        trial_runner=regression_trial))
    assert result["trials"] == 3
    assert result["best"]["score"] == 8.0
    assert result["target_selections"]["excellent"]["trial_id"] == 2
    assert result["milestone"] is None and result["stretch"] is None
    assert result["problem_hash"] == regression_problem.fingerprint
    instructions = observed[0][0][0]["content"]
    assert regression_problem.brief in instructions and "rmse (minimize)" in instructions
    assert regression_problem.fingerprint in instructions and "ROC-AUC" not in instructions
    analysis_tool = next(t for t in observed[0][1] if t["function"]["name"] == "run_analysis")
    scientific_schema = json.loads(json.dumps(analysis_tool["function"]["parameters"]))
    assert "intent" in scientific_schema["required"]
    scientific_schema["required"].remove("intent")
    scientific_schema["properties"].pop("intent")
    assert scientific_schema == get_adapter(regression_problem).analysis_schema
    frozen = json.loads((directory / "resolved-config.json").read_text())
    assert frozen["problem"] == regression_problem.to_dict()
    assert frozen["problem_hash"] == regression_problem.fingerprint
    assert result["data_fingerprint"] == manifest["data_fingerprint"]
    assert frozen["data_fingerprint"] == manifest["data_fingerprint"]
    assert json.loads((directory / "checkpoint.json").read_text())["data_fingerprint"] == manifest["data_fingerprint"]
    started = json.loads((directory / "events.jsonl").read_text().splitlines()[0])
    assert started["data_fingerprint"] == manifest["data_fingerprint"]

    # Crash recovery uses run science even when the prepared dataset is unavailable.
    (directory / "summary.json").unlink()
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    (directory / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events
                                               if e["type"] != "run_stopped"))
    data.rename(tmp_path / "unavailable-data")
    recovered = recover_run(directory)
    assert recovered["data_fingerprint"] == manifest["data_fingerprint"]
    assert recovered["objective"] == regression_problem.objective
    assert recovered["problem_hash"] == regression_problem.fingerprint
    assert recovered["best"]["trial_id"] == 2
    assert recovered["target_selections"]["excellent"]["trial_id"] == 2


def test_changed_profile_is_rejected_before_controller_model_call(tmp_path, regression_problem):
    from study.problem import ProblemSpec
    from study.science import prepare_dataset
    data = tmp_path / "data"
    prepare_dataset(data, problem=regression_problem)
    changed = regression_problem.to_dict()
    changed["brief"] += " Changed science."
    model = ScriptedModel()
    with pytest.raises(ValueError, match="frozen|differs|match"):
        asyncio.run(run_one(StudyConfig(), data, tmp_path / "run", model,
            trial_runner=trial, problem=ProblemSpec.from_dict(changed)))
    assert model.roles == []
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("metric,direction,score", [("accuracy", "maximize", 1.1),
    ("rmse", "minimize", -1.0), ("r2", "maximize", 1.1)])
def test_selection_respects_objective_metric_bounds(metric, direction, score):
    from types import SimpleNamespace
    from study.selection import select_result
    from study.events import Accounting
    summary = {"best": None, "target_selections": {}}
    select_result(summary, {"status": "completed", "score": score, "metrics": {metric: score},
        "trial_id": 1, "elapsed_seconds": 1, "artifact": "fit", "artifact_hash": "hash"},
        Accounting(), StudyConfig(), problem=SimpleNamespace(
            objective={"metric": metric, "direction": direction}, targets=[]))
    assert summary["best"] is None


def test_recovery_uses_frozen_budget_and_checks_problem_hash(tmp_path):
    run_dir = tmp_path / "run"
    asyncio.run(run_one(StudyConfig(trial_cap=1), tmp_path, run_dir, ScriptedModel(),
        trial_runner=trial, project={}))
    (run_dir / "summary.json").unlink()
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    (run_dir / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events
        if e["type"] != "run_stopped"))
    (run_dir / "config.json").write_text(json.dumps({"allowance_seconds": "invalid later edit"}))
    recovered = recover_run(run_dir)
    assert recovered["best"]["validation_auc"] == .96
    assert recovered["allowance_seconds"] == 900
    (run_dir / "summary.json").unlink()
    frozen = json.loads((run_dir / "resolved-config.json").read_text())
    frozen["problem_hash"] = "tampered"
    (run_dir / "resolved-config.json").write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match="fingerprint"):
        recover_run(run_dir)
