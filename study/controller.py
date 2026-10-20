"""The harness, not the model, controls experimental timing and treatments."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import time

from .config import StudyConfig
from .events import Accounting, Journal, atomic_json, read_events, utc_now
from . import prompts


class StopRun(Exception):
    pass


def function_tool(name, description, parameters):
    return {"type": "function", "function": {"name": name, "description": description,
                                           "parameters": parameters}}


EMPTY = {"type": "object", "properties": {}, "additionalProperties": False}


def tools_for(role, config, problem=None):
    if role == "reflection":
        return []
    tools = [
        function_tool("inspect_project", "Read fixed task and search-space metadata.", EMPTY),
        function_tool("read_results", "Read the common bounded recent-trial history.", EMPTY),
    ]
    if role == "researcher":
        if problem is None:
            from .science import ANALYSIS_SCHEMA
            schema = ANALYSIS_SCHEMA
        else:
            from .tasks import get_adapter
            schema = get_adapter(problem).analysis_schema
        from copy import deepcopy
        from .reasoning import contract_schema
        schema = deepcopy(schema)
        schema["properties"]["intent"] = contract_schema("researcher", config.lesson_memory)
        schema["required"] = [*schema["required"], "intent"]
        tools.append(function_tool("run_analysis", "Run exactly one bounded experiment.", schema))
    if role == "supervisor" and config.literature:
        for name, field, description in (
            ("literature_search", "query", "Search scholarly literature for a specific uncertainty."),
            ("literature_fetch", "url", "Read a public source and retain supporting passages."),
        ):
            tools.append(function_tool(name, description, {"type": "object", "properties": {
                field: {"type": "string", "minLength": 1, "maxLength": 2000}},
                "required": [field], "additionalProperties": False}))
    return tools


def agent_result(result):
    return {key: value for key, value in result.items()
            if key not in ("artifact", "artifact_hash", "fingerprint", "provenance")}


def resolve_problem(config, data_dir, problem=None):
    """Resolve and verify science before starting any model or allowance clock."""
    from .problem import ProblemSpec, assert_problem_matches, legacy_problem, problem_from_data
    frozen = problem_from_data(data_dir)
    if problem is not None:
        if isinstance(problem, dict):
            problem = ProblemSpec.from_dict(problem)
        assert_problem_matches(data_dir, problem)
        return problem
    if frozen is not None:
        assert_problem_matches(data_dir, frozen)
        return frozen
    return legacy_problem(milestone=config.milestone, stretch=config.stretch)


def prepared_fingerprint(data_dir):
    """Return prepared content identity; fixture-only legacy runs may have none."""
    manifest = Path(data_dir) / "manifest.json"
    return json.loads(manifest.read_text()).get("data_fingerprint") if manifest.exists() else None


def initial_summary(config, problem, data_fingerprint=None):
    return {"condition": config.condition, "repeat": config.repeat,
        "allowance_seconds": config.allowance_seconds, "config": config.to_dict(),
        "problem": problem.to_dict(), "problem_hash": problem.fingerprint,
        "data_fingerprint": data_fingerprint, "objective": dict(problem.objective), "target_definitions": problem.targets,
        "target_selections": {target["name"]: None for target in problem.targets},
        "trials": 0, "best": None, "milestone": None, "stretch": None,
        "training_seconds": 0.0}


def select_result(summary, result, accounting, config, problem=None):
    if result.get("status") != "completed":
        return
    objective = problem.objective if problem is not None else {"metric": "roc_auc", "direction": "maximize"}
    metric = objective["metric"]
    score = result.get("score", result.get("metrics", {}).get(metric))
    if score is None and metric == "roc_auc":
        score = result.get("validation_auc")
    if type(score) not in (float, int) or not math.isfinite(score):
        return
    from .problem import validate_metric_value
    try:
        validate_metric_value(metric, score)
    except (ValueError, KeyError):
        return
    elapsed = result.get("elapsed_seconds")
    if type(elapsed) not in (float, int) or not math.isfinite(elapsed) or not 0 <= elapsed <= config.allowance_seconds:
        return
    selected = {key: result[key] for key in (
        "trial_id", "elapsed_seconds", "artifact", "artifact_hash")}
    if "config" in result:
        selected["config"] = result["config"]
    selected.update(score=score, metrics=dict(result.get("metrics") or {metric: score}),
                    accounting=accounting.snapshot())
    if metric == "roc_auc":
        selected["validation_auc"] = score
    minimize = objective["direction"] == "minimize"
    best = summary.get("best")
    previous_score = best.get("score", best.get("validation_auc")) if best else None
    better = previous_score is None or (score < previous_score if minimize else score > previous_score)
    if better or (score == previous_score and elapsed < best["elapsed_seconds"]):
        summary["best"] = selected
    targets = problem.targets if problem is not None else [
        {"name": "milestone", "value": config.milestone}, {"name": "stretch", "value": config.stretch}]
    selections = summary.setdefault("target_selections", {})
    for target in targets:
        name, threshold = target["name"], target["value"]
        reached = score <= threshold if minimize else score >= threshold
        previous = selections.get(name, summary.get(name) if name in ("milestone", "stretch") else None)
        if reached and (previous is None or elapsed < previous["elapsed_seconds"]):
            selections[name] = selected
            if name in ("milestone", "stretch"):
                summary[name] = selected
        else:
            selections.setdefault(name, previous)


async def run_one(config, data_dir, run_dir, model, *, trial_runner=None, project=None, literature=None,
                  provider_metadata=None, problem=None, progress=None):
    """Run once in a NEW directory. Existing runs must be recovered, never resumed."""
    if trial_runner is None:
        from .science import run_trial
        trial_runner = run_trial
        if config.max_cores is not None:
            from .resources import CorePool, BalancedTrials
            trial_runner = BalancedTrials(CorePool(config.max_cores))
    run_dir, data_dir = Path(run_dir).resolve(), Path(data_dir).resolve()
    problem = resolve_problem(config, data_dir, problem)
    data_fingerprint = prepared_fingerprint(data_dir)
    if project is None:
        from .problem import problem_from_data
        if problem_from_data(data_dir) is not None:
            from .tasks import get_adapter
            project = get_adapter(problem).describe(data_dir)
        else:
            from .science import project_info
            project = project_info(data_dir)
    # Provisioning happens before the allowance clock starts.
    run_dir.mkdir(parents=True, exist_ok=False)
    atomic_json(run_dir / "config.json", config.to_dict())
    atomic_json(run_dir / "project.json", project)
    atomic_json(run_dir / "problem.json", problem.to_dict())
    atomic_json(run_dir / "resolved-config.json", {"config": config.to_dict(),
        "problem": problem.to_dict(), "problem_hash": problem.fingerprint,
        "data_fingerprint": data_fingerprint})
    if provider_metadata is not None:
        atomic_json(run_dir / "provider.json", provider_metadata)
    history = []
    from .reasoning import LessonMemory, validate_contract, parse_contract, schema_errors, ground_contract
    memory = LessonMemory(config.memory_limit)
    feedback = reflection = None
    accounting = Accounting()
    model_seconds = 0.0
    summary = initial_summary(config, problem, data_fingerprint)
    started = time.monotonic()
    deadline = started + config.allowance_seconds
    journal = Journal(run_dir, started, progress=progress)
    journal.emit("run_started", config=config.to_dict(), project=project,
                 problem=problem.to_dict(), problem_hash=problem.fingerprint,
                 data_fingerprint=data_fingerprint,
                 deadline_utc=(datetime.now(timezone.utc) + timedelta(seconds=config.allowance_seconds)).isoformat())

    def remaining():
        return deadline - time.monotonic()

    def check():
        if remaining() <= 0:
            raise StopRun("deadline")
        if accounting.known_cost >= config.dollar_cap:
            raise StopRun("dollar_cap")
        if not accounting.cost_complete and not config.allow_unknown_cost:
            raise StopRun("unknown_cost")
        if summary["trials"] >= config.trial_cap:
            raise StopRun("trial_cap")

    def context():
        return json.dumps({"project": project, "recent_trials": [agent_result(row) for row in history[-config.history_trials:]],
            "best": agent_result(summary["best"] or {}), "last_supervisor_feedback": feedback,
            "last_explicit_reflection": reflection, "trials_attempted": summary["trials"],
            "trial_cap": config.trial_cap, "remaining_trials": max(0, config.trial_cap - summary["trials"]),
            "remaining_seconds": max(0, remaining()), "accounting": accounting.snapshot(),
            "mean_model_call_seconds": model_seconds / accounting.calls if accounting.calls else None,
            "review_every_trials": config.review_every, "reflection_after_each_trial": config.reflection,
            "objective": problem.objective,
            "targets": {target["name"]: target["value"] for target in problem.targets},
            **({"lessons": memory.snapshot()} if config.lesson_memory else {})},
            allow_nan=False)

    async def model_call(role, messages, tools):
        nonlocal model_seconds
        for attempt in range(config.model_retries + 1):
            check()
            available = remaining()
            if available < config.model_start_buffer_seconds:
                journal.emit("model_call_skipped", role=role, reason="deadline_buffer",
                             remaining_seconds=max(0, available),
                             model_start_buffer_seconds=config.model_start_buffer_seconds)
                raise StopRun("deadline")
            # Replace the initial snapshot, rather than appending duplicate
            # history. Tool turns and repairs must see current budgets too.
            messages[1] = {"role": "user", "content": context()}
            begin = time.monotonic()
            journal.emit("model_call_started", role=role, attempt=attempt, messages=messages, tools=tools)
            try:
                response = await asyncio.wait_for(model.complete(messages, tools,
                    timeout=min(remaining(), config.model_timeout_seconds)),
                    timeout=min(remaining(), config.model_timeout_seconds))
            except asyncio.CancelledError:
                model_seconds += time.monotonic() - begin
                accounting.add(None)
                journal.emit("model_call", role=role, attempt=attempt, status="cancelled",
                    usage=None, accounting=accounting.snapshot(), duration_seconds=time.monotonic() - begin)
                raise
            except Exception as error:
                model_seconds += time.monotonic() - begin
                details = getattr(error, "details", {})
                usage = details.get("usage")
                accounting.add(usage)
                journal.emit("model_call", role=role, attempt=attempt, status="failed",
                    error=type(error).__name__, details=details, usage=usage,
                    accounting=accounting.snapshot(),
                    duration_seconds=time.monotonic() - begin)
                check()
                if attempt == config.model_retries:
                    raise StopRun("model_failure") from error
                continue
            model_seconds += time.monotonic() - begin
            accounting.add(response.get("usage"))
            journal.emit("model_call", role=role, attempt=attempt, status="completed",
                         response=response, usage=response.get("usage"),
                         accounting=accounting.snapshot(),
                         duration_seconds=time.monotonic() - begin)
            check()
            return response["message"]

    def accept_lessons(contract):
        if config.lesson_memory and contract.get("lesson_updates"):
            memory.update(contract["lesson_updates"], history)
            journal.emit("lesson_memory", lessons=memory.snapshot())
            atomic_json(run_dir / "lessons.json", {"scope": "this run only", "lessons": memory.snapshot()})

    def ground_accepted(contract, role):
        contract, changes = ground_contract(contract)
        if changes:
            journal.emit("contract_grounded", role=role, adjustments=changes)
        return contract

    async def phase(role):
        instructions = prompts.instructions_for(role, problem)
        from .reasoning import instructions as contract_instructions
        instructions += contract_instructions(role, memory=config.lesson_memory)
        tools = tools_for(role, config, problem)
        schemas = {tool["function"]["name"]: tool["function"]["parameters"] for tool in tools}
        messages = [{"role": "system", "content": instructions},
                    {"role": "user", "content": context()}]
        browser_calls = other_calls = 0
        seen_calls = {}
        turns = config.max_turns_without_trial if role == "researcher" else config.review_tool_calls + 1
        for _ in range(turns):
            message = await model_call(role, messages, tools)
            messages.append(message)
            calls = message.get("tool_calls") or []
            if not calls:
                if role != "researcher":
                    contract = None
                    try:
                        contract = parse_contract(message.get("content"), allow_wrapper=True)
                        errors = validate_contract(contract, role, history,
                            has_feedback=feedback is not None, memory=config.lesson_memory)
                        if not errors:
                            contract = ground_accepted(contract, role)
                    except (ValueError, TypeError) as error:
                        errors = [str(error)]
                    journal.emit(role + "_contract", after_trial=summary["trials"],
                                 contract=contract, valid=not errors, errors=errors)
                    if errors:
                        # The review has finished gathering evidence. Repairs
                        # only need the recorded measurements and format limits.
                        tools, schemas = [], {}
                        messages.append({"role": "user", "content":
                            "Correct the contract using the evidence already supplied. Return only the JSON object, "
                            "without a preamble or code fence. " + " ".join(errors)})
                        continue
                    accept_lessons(contract)
                    return contract
                messages.append({"role": "user", "content": "Choose the next experiment with run_analysis."})
                continue
            # Multiple classifier calls would change review cadence. Reject the entire
            # response rather than silently executing an unreviewed batch.
            multiple_trials = sum(c.get("function", {}).get("name") == "run_analysis" for c in calls) > 1
            for call in calls:
                check()
                name = call.get("function", {}).get("name", "")
                raw_args = call.get("function", {}).get("arguments", "{}")
                result = None
                args = None
                contract_recorded = False
                try:
                    import jsonschema
                    args = parse_contract(raw_args)
                    if name not in schemas:
                        raise ValueError("Tool not permitted for this role")
                    errors = schema_errors(args, schemas[name], name + " arguments")
                    if errors:
                        raise ValueError(" ".join(errors))
                    if multiple_trials:
                        raise ValueError("Call at most one run_analysis per decision")
                    call_key = (name, json.dumps(args, sort_keys=True, separators=(",", ":")))
                    seen_calls[call_key] = seen_calls.get(call_key, 0) + 1
                    if seen_calls[call_key] > 1:
                        journal.emit("repeated_tool_call", role=role, name=name,
                                     repetitions=seen_calls[call_key], arguments=args)
                    if name == "run_analysis":
                        intent = args.pop("intent", None)
                        errors = validate_contract(intent, "researcher", history,
                            has_feedback=feedback is not None, memory=config.lesson_memory)
                        if not errors:
                            intent = ground_accepted(intent, "researcher")
                        journal.emit("decision_contract", trial_id=summary["trials"] + 1,
                                     contract=intent, valid=not errors, errors=errors)
                        contract_recorded = True
                        if errors:
                            raise ValueError("Correct the decision contract: " + " ".join(errors))
                        accept_lessons(intent)
                        from .diagnostics import experiment_diagnostic
                        diagnostic = experiment_diagnostic(args, problem=problem, project=project,
                                                           seed=config.training_seed, history=history)
                        summary["trials"] += 1
                        trial_id = summary["trials"]
                        journal.emit("decision", trial_id=trial_id, message=message,
                                     supervisor_feedback=feedback, explicit_reflection=reflection)
                        journal.emit("experiment_diagnostic", trial_id=trial_id, **diagnostic)
                        journal.emit("trial_started", trial_id=trial_id, config=args,
                                     intent=intent)
                        begin = time.monotonic()
                        trial_limit = min(remaining(), config.trial_timeout_seconds)
                        resource_kwargs = {}
                        allocation = {}
                        from .resources import BalancedTrials
                        if isinstance(trial_runner, BalancedTrials):
                            def resource_status(**status):
                                if status["allocated_cores"]:
                                    allocation.update(started=time.monotonic(), cores=status["allocated_cores"])
                                journal.emit("resources", **status)
                            resource_kwargs["resource_callback"] = resource_status
                        try:
                            result = await asyncio.wait_for(trial_runner(data_dir,
                                run_dir / "trials" / f"{trial_id:04d}", args,
                                seed=config.training_seed, timeout=trial_limit, **resource_kwargs), timeout=trial_limit)
                        except TimeoutError:
                            result = {"status": "timeout", "error": "Trial exceeded allotted time"}
                        except Exception as error:
                            result = {"status": "failed", "error": f"{type(error).__name__}: {error}"}
                        duration = time.monotonic() - begin
                        training_duration = duration
                        if resource_kwargs:
                            queued = allocation.get("started", time.monotonic()) - begin
                            result.update(queue_seconds=queued, allocated_cores=allocation.get("cores", 0))
                            training_duration = max(0, duration - queued)
                        summary["training_seconds"] += training_duration
                        for key in ("effective_config", "fingerprint", "provenance"):
                            result.setdefault(key, diagnostic[key])
                        result["experiment_diagnostic"] = {key: diagnostic[key] for key in ("equivalent_trial_ids", "warning")}
                        result.update(trial_id=trial_id, config=args, seed=config.training_seed,
                                      elapsed_seconds=time.monotonic() - started,
                                      duration_seconds=duration, training_seconds=training_duration)
                        if remaining() <= 0 and result["status"] == "completed":
                            result["status"] = "late"
                        journal.emit("trial_finished", result=result)
                        select_result(summary, result, accounting, config, problem)
                        journal.emit("selection", best=summary["best"], milestone=summary["milestone"],
                                     stretch=summary["stretch"], target_selections=summary["target_selections"])
                        atomic_json(run_dir / "checkpoint.json", summary)
                        history.append(result)
                        return agent_result(result)
                    if name == "inspect_project":
                        result = project
                    elif name == "read_results":
                        result = [agent_result(row) for row in history[-config.history_trials:]]
                    elif name.startswith("literature_"):
                        if browser_calls >= config.literature_calls_per_review:
                            raise ValueError("Per-review literature cap reached")
                        browser_calls += 1
                        if literature is None:
                            from .literature import LiteratureClient
                            # Default client created per call to keep ownership local.
                            client = LiteratureClient()
                        else:
                            client = literature
                        limit = min(remaining(), config.literature_timeout_seconds)
                        try:
                            operation = client.search(args["query"], timeout=limit) if name == "literature_search" else client.fetch(args["url"], timeout=limit)
                            # The client bounds DNS, all redirect hops and body
                            # reads together, retaining evidence on timeout.
                            # A competing outer timer would erase those details.
                            result = await operation
                        finally:
                            if literature is None and hasattr(client, "aclose"):
                                await client.aclose()
                    other_calls += 1
                    if role == "supervisor" and other_calls >= config.review_tool_calls:
                        tools = []
                        schemas = {}
                except Exception as error:
                    detail = error.message if isinstance(error, jsonschema.ValidationError) else str(error)
                    result = {"error": f"{type(error).__name__}: {detail}"}
                    if name == "run_analysis" and not contract_recorded:
                        journal.emit("decision_contract", trial_id=summary["trials"] + 1,
                                     contract=args.get("intent") if isinstance(args, dict) else None,
                                     valid=False, errors=[result["error"]])
                    if name.startswith("literature_") and getattr(error, "details", None):
                        result["evidence"] = error.details
                journal.emit("tool_call", role=role, name=name, arguments=raw_args, result=result)
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                 "content": json.dumps(result, allow_nan=False)})
        if role == "researcher":
            raise StopRun("no_progress")
        raise StopRun("invalid_contract")

    stop_reason = "failure"
    try:
        while True:
            check()
            await phase("researcher")
            check()  # No treatment calls if a safeguard/deadline precludes another trial.
            if config.review_every and summary["trials"] % config.review_every == 0:
                feedback = await phase("supervisor")
                journal.emit("review", after_trial=summary["trials"],
                             feedback=feedback["summary"], contract=feedback)
            if config.reflection:
                reflection = await phase("reflection")
                journal.emit("reflection", after_trial=summary["trials"],
                             reflection=reflection["summary"], contract=reflection)
    except StopRun as stop:
        stop_reason = str(stop)
    except asyncio.CancelledError:
        stop_reason = "interrupted"
        raise
    except Exception as error:
        journal.emit("failure", error=f"{type(error).__name__}: {error}")
    finally:
        if config.lesson_memory:
            summary["lessons"] = memory.snapshot()
        summary.update(stop_reason=stop_reason, elapsed_seconds=time.monotonic() - started,
                       accounting=accounting.snapshot())
        journal.emit("run_stopped", summary=summary)
        atomic_json(run_dir / "summary.json", summary)
    return summary


def recover_run(run_dir):
    """Freeze a crashed run from committed events; never grant more search time."""
    run_dir = Path(run_dir)
    if (run_dir / "summary.json").exists():
        return json.loads((run_dir / "summary.json").read_text())
    events = read_events(run_dir / "events.jsonl")
    stopped = next((e for e in reversed(events) if e["type"] == "run_stopped"), None)
    if stopped:
        atomic_json(run_dir / "summary.json", stopped["summary"])
        return stopped["summary"]
    from .problem import ProblemSpec, legacy_problem
    data_fingerprint = next((event.get("data_fingerprint") for event in events
                             if event["type"] == "run_started"), None)
    frozen_path = run_dir / "resolved-config.json"
    if frozen_path.exists():
        frozen = json.loads(frozen_path.read_text())
        recorded_config = frozen["config"]
        config = StudyConfig(**{**recorded_config, "decision_protocol": "structured_v1"})
        data_fingerprint = frozen.get("data_fingerprint", data_fingerprint)
        problem = ProblemSpec.from_dict(frozen["problem"])
        if problem.fingerprint != frozen["problem_hash"]:
            raise ValueError("Frozen run problem fingerprint does not match")
    else:
        recorded_config = json.loads((run_dir / "config.json").read_text())
        config = StudyConfig(**{**recorded_config, "decision_protocol": "structured_v1"})
        if (run_dir / "problem.json").exists():
            problem = ProblemSpec.from_dict(json.loads((run_dir / "problem.json").read_text()))
        else:
            problem = legacy_problem(milestone=config.milestone, stretch=config.stretch)
    summary = initial_summary(config, problem, data_fingerprint)
    summary["config"] = {**recorded_config, "decision_protocol": recorded_config.get("decision_protocol", "legacy")}
    if config.lesson_memory:
        summary["lessons"] = []
    accounting = Accounting()
    started_calls = finished_calls = 0
    for event in events:
        if event["type"] == "model_call_started":
            started_calls += 1
        elif event["type"] == "model_call":
            finished_calls += 1
            accounting.add(event.get("usage"))
        elif event["type"] == "lesson_memory" and config.lesson_memory:
            summary["lessons"] = event["lessons"]
        elif event["type"] == "trial_started":
            summary["trials"] += 1
        elif event["type"] == "trial_finished":
            result = event["result"]
            summary["training_seconds"] += result.get("training_seconds", result.get("duration_seconds", 0))
            select_result(summary, result, accounting, config, problem)
    for _ in range(started_calls - finished_calls):
        accounting.add(None)  # An in-flight request may have been billed.
    summary.update(stop_reason="interrupted", elapsed_seconds=events[-1]["elapsed_seconds"] if events else 0,
                   accounting=accounting.snapshot(), recovered_at=utc_now())
    atomic_json(run_dir / "summary.json", summary)
    return summary
