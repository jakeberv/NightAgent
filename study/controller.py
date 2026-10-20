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


def tools_for(role, config):
    if role == "reflection":
        return []
    tools = [
        function_tool("inspect_project", "Read fixed task and search-space metadata.", EMPTY),
        function_tool("read_results", "Read the common bounded recent-trial history.", EMPTY),
    ]
    if role == "researcher":
        from .science import ANALYSIS_SCHEMA
        tools.append(function_tool("run_analysis", "Run exactly one bounded classifier trial.", ANALYSIS_SCHEMA))
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
            if key not in ("artifact", "artifact_hash")}


def select_result(summary, result, accounting, config):
    if result.get("status") != "completed":
        return
    score = result.get("validation_auc")
    if type(score) not in (float, int) or not math.isfinite(score) or not 0 <= score <= 1:
        return
    if result["elapsed_seconds"] > config.allowance_seconds:
        return
    selected = {key: result[key] for key in (
        "trial_id", "elapsed_seconds", "validation_auc", "artifact", "artifact_hash")}
    selected["accounting"] = accounting.snapshot()
    if summary["best"] is None or score > summary["best"]["validation_auc"]:
        summary["best"] = selected
    for name, threshold in (("milestone", config.milestone), ("stretch", config.stretch)):
        if summary[name] is None and score >= threshold:
            summary[name] = selected


async def run_one(config, data_dir, run_dir, model, *, trial_runner=None, project=None, literature=None,
                  provider_metadata=None):
    """Run once in a NEW directory. Existing runs must be recovered, never resumed."""
    from .science import project_info, run_trial
    if trial_runner is None:
        trial_runner = run_trial
    run_dir, data_dir = Path(run_dir).resolve(), Path(data_dir).resolve()
    if project is None:
        project = project_info(data_dir)
    # Provisioning happens before the allowance clock starts.
    run_dir.mkdir(parents=True, exist_ok=False)
    atomic_json(run_dir / "config.json", config.to_dict())
    atomic_json(run_dir / "project.json", project)
    if provider_metadata is not None:
        atomic_json(run_dir / "provider.json", provider_metadata)
    history = []
    feedback = reflection = None
    accounting = Accounting()
    summary = {"condition": config.condition, "repeat": config.repeat,
               "allowance_seconds": config.allowance_seconds, "config": config.to_dict(),
               "trials": 0, "best": None, "milestone": None, "stretch": None, "training_seconds": 0.0}
    started = time.monotonic()
    deadline = started + config.allowance_seconds
    journal = Journal(run_dir, started)
    journal.emit("run_started", config=config.to_dict(), project=project,
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
        return json.dumps({"project": project, "recent_trials": history[-config.history_trials:],
            "best": agent_result(summary["best"] or {}), "last_supervisor_feedback": feedback,
            "last_explicit_reflection": reflection, "trials_attempted": summary["trials"],
            "remaining_seconds": max(0, remaining()), "accounting": accounting.snapshot(),
            "targets": {"milestone": config.milestone, "stretch": config.stretch}},
            allow_nan=False)

    async def model_call(role, messages, tools):
        for attempt in range(config.model_retries + 1):
            check()
            begin = time.monotonic()
            journal.emit("model_call_started", role=role, attempt=attempt, messages=messages, tools=tools)
            try:
                response = await asyncio.wait_for(model.complete(messages, tools,
                    timeout=min(remaining(), config.model_timeout_seconds)),
                    timeout=min(remaining(), config.model_timeout_seconds))
            except asyncio.CancelledError:
                accounting.add(None)
                journal.emit("model_call", role=role, attempt=attempt, status="cancelled",
                    usage=None, duration_seconds=time.monotonic() - begin)
                raise
            except Exception as error:
                details = getattr(error, "details", {})
                usage = details.get("usage")
                accounting.add(usage)
                journal.emit("model_call", role=role, attempt=attempt, status="failed",
                    error=type(error).__name__, details=details, usage=usage,
                    duration_seconds=time.monotonic() - begin)
                check()
                if attempt == config.model_retries:
                    raise StopRun("model_failure") from error
                continue
            accounting.add(response.get("usage"))
            journal.emit("model_call", role=role, attempt=attempt, status="completed",
                         response=response, usage=response.get("usage"),
                         duration_seconds=time.monotonic() - begin)
            check()
            return response["message"]

    async def phase(role):
        instructions = {"researcher": prompts.RESEARCHER, "supervisor": prompts.SUPERVISOR,
                        "reflection": prompts.REFLECTION}[role]
        tools = tools_for(role, config)
        schemas = {tool["function"]["name"]: tool["function"]["parameters"] for tool in tools}
        messages = [{"role": "system", "content": instructions},
                    {"role": "user", "content": context()}]
        browser_calls = other_calls = 0
        turns = config.max_turns_without_trial if role == "researcher" else config.review_tool_calls + 1
        for _ in range(turns):
            message = await model_call(role, messages, tools)
            messages.append(message)
            calls = message.get("tool_calls") or []
            if not calls:
                if role != "researcher":
                    return message.get("content") or ""
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
                try:
                    import jsonschema
                    args = json.loads(raw_args)
                    if name not in schemas:
                        raise ValueError("Tool not permitted for this role")
                    jsonschema.validate(args, schemas[name])
                    if multiple_trials:
                        raise ValueError("Call at most one run_analysis per decision")
                    if name == "run_analysis":
                        summary["trials"] += 1
                        trial_id = summary["trials"]
                        journal.emit("decision", trial_id=trial_id, message=message,
                                     supervisor_feedback=feedback, explicit_reflection=reflection)
                        journal.emit("trial_started", trial_id=trial_id, config=args)
                        begin = time.monotonic()
                        trial_limit = min(remaining(), config.trial_timeout_seconds)
                        try:
                            result = await asyncio.wait_for(trial_runner(data_dir,
                                run_dir / "trials" / f"{trial_id:04d}", args,
                                seed=config.training_seed, timeout=trial_limit), timeout=trial_limit)
                        except TimeoutError:
                            result = {"status": "timeout", "error": "Trial exceeded allotted time"}
                        except Exception as error:
                            result = {"status": "failed", "error": f"{type(error).__name__}: {error}"}
                        duration = time.monotonic() - begin
                        summary["training_seconds"] += duration
                        result.update(trial_id=trial_id, config=args, elapsed_seconds=time.monotonic() - started,
                                      duration_seconds=duration)
                        if remaining() <= 0 and result["status"] == "completed":
                            result["status"] = "late"
                        journal.emit("trial_finished", result=result)
                        select_result(summary, result, accounting, config)
                        journal.emit("selection", best=summary["best"], milestone=summary["milestone"],
                                     stretch=summary["stretch"])
                        atomic_json(run_dir / "checkpoint.json", summary)
                        history.append(agent_result(result))
                        return agent_result(result)
                    if name == "inspect_project":
                        result = project
                    elif name == "read_results":
                        result = history[-config.history_trials:]
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
                            result = await asyncio.wait_for(operation, timeout=limit)
                        finally:
                            if literature is None and hasattr(client, "aclose"):
                                await client.aclose()
                    other_calls += 1
                    if role == "supervisor" and other_calls >= config.review_tool_calls:
                        tools = []
                        schemas = {}
                except Exception as error:
                    result = {"error": f"{type(error).__name__}: {error}"}
                journal.emit("tool_call", role=role, name=name, arguments=raw_args, result=result)
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                 "content": json.dumps(result, allow_nan=False)})
        if role == "researcher":
            raise StopRun("no_progress")
        return "Review/reflection call limit reached; consult logged evidence."

    stop_reason = "failure"
    try:
        while True:
            check()
            await phase("researcher")
            check()  # No treatment calls if a safeguard/deadline precludes another trial.
            if config.review_every and summary["trials"] % config.review_every == 0:
                feedback = await phase("supervisor")
                journal.emit("review", after_trial=summary["trials"], feedback=feedback)
            if config.reflection:
                reflection = await phase("reflection")
                journal.emit("reflection", after_trial=summary["trials"], reflection=reflection)
    except StopRun as stop:
        stop_reason = str(stop)
    except asyncio.CancelledError:
        stop_reason = "interrupted"
        raise
    except Exception as error:
        journal.emit("failure", error=f"{type(error).__name__}: {error}")
    finally:
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
    config = StudyConfig(**json.loads((run_dir / "config.json").read_text()))
    summary = {"condition": config.condition, "repeat": config.repeat,
        "config": config.to_dict(), "allowance_seconds": config.allowance_seconds,
        "trials": 0, "best": None, "milestone": None, "stretch": None, "training_seconds": 0.0}
    accounting = Accounting()
    started_calls = finished_calls = 0
    for event in events:
        if event["type"] == "model_call_started":
            started_calls += 1
        elif event["type"] == "model_call":
            finished_calls += 1
            accounting.add(event.get("usage"))
        elif event["type"] == "trial_started":
            summary["trials"] += 1
        elif event["type"] == "trial_finished":
            result = event["result"]
            summary["training_seconds"] += result.get("duration_seconds", 0)
            select_result(summary, result, accounting, config)
    for _ in range(started_calls - finished_calls):
        accounting.add(None)  # An in-flight request may have been billed.
    summary.update(stop_reason="interrupted", elapsed_seconds=events[-1]["elapsed_seconds"] if events else 0,
                   accounting=accounting.snapshot(), recovered_at=utc_now())
    atomic_json(run_dir / "summary.json", summary)
    return summary
