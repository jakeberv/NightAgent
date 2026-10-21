"""The harness, not the model, controls experimental timing and treatments."""
import asyncio
from datetime import datetime, timedelta, timezone
from dataclasses import replace
import json
from pathlib import Path
import time

from .events import Journal, atomic_json
from . import prompts, model_tools
from .model_calls import ModelCalls
from .run_context import build_context, compact_result, required_start_seconds
from .run_state import RunState, StopRun
from .trial_execution import TrialExecutor


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


def execution_config(config, problem):
    """Resolve the neural backend before model calls; explicit MPS never falls back."""
    if problem and any(name.startswith('torch_') for name in problem.search_space['models']):
        from .torch_models import resolve_device
        return replace(config, device=resolve_device(config.device))
    return replace(config, device='cpu')


async def run_one(config, data_dir, run_dir, model, *, trial_runner=None, project=None, literature=None,
                  provider_metadata=None, problem=None, progress=None):
    """Run once in a NEW directory. Existing runs must be recovered, never resumed."""
    problem = resolve_problem(config, data_dir, problem)
    config = execution_config(config, problem)
    if trial_runner is None:
        from .resources import CorePool, BalancedTrials
        trial_runner = BalancedTrials(CorePool(config.max_cores or 1), device=config.device)
    run_dir, data_dir = Path(run_dir).resolve(), Path(data_dir).resolve()
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
    from .tasks import get_adapter
    permitted_experiments = get_adapter(problem).analysis_schema
    from .reasoning import LessonMemory, validate_contract, parse_contract, schema_errors, ground_contract, resolve_contract_evidence, request_contract_schema, lesson_update_required
    memory = LessonMemory(config.memory_limit)
    state = RunState(config, problem, clock=time.monotonic,
                     data_fingerprint=data_fingerprint)
    summary, history, accounting = state.summary, state.history, state.accounting
    journal = Journal(run_dir, state.started, progress=progress)
    journal.emit("run_started", config=config.to_dict(), project=project,
                 problem=problem.to_dict(), problem_hash=problem.fingerprint,
                 data_fingerprint=data_fingerprint,
                 deadline_utc=(datetime.now(timezone.utc) + timedelta(seconds=config.allowance_seconds)).isoformat())

    reuse_feedback = {'count': 0, 'latest': None}

    def context(role=None, *, framing=False):
        return build_context(state, project=project, permitted_experiments=permitted_experiments,
                             memory=memory, role=role, framing=framing, reuse_feedback=reuse_feedback)

    model_call = ModelCalls(state=state, journal=journal, model=model, context=context)
    trial_executor = TrialExecutor(state=state, journal=journal, trial_runner=trial_runner,
                                   data_dir=data_dir, run_dir=run_dir)

    def accept_lessons(contract):
        if config.lesson_memory and contract.get("lesson_updates"):
            memory.update(contract["lesson_updates"], history)
            journal.emit("lesson_memory", lessons=memory.snapshot())
            atomic_json(run_dir / "lessons.json", {"scope": "this run only", "lessons": memory.snapshot()})

    def ground_accepted(contract, role, *, framing=False, require_lesson_update=False):
        contract, changes = ground_contract(contract, history=history, targets=state.targets(),
                                            capacity=state.capacity(role, framing, phase_completed=True))
        errors = validate_contract(contract, role, history, has_feedback=state.feedback is not None,
            memory=config.lesson_memory, supervisor_strategy=config.supervisor_strategy, framing=framing,
            require_lesson_update=require_lesson_update)
        if errors:
            journal.emit("failure", error="Runner-generated contract failed validation", details=errors)
            raise StopRun("invalid_grounded_contract")
        if changes:
            journal.emit("contract_grounded", role=role, adjustments=changes)
        return contract

    async def phase(role, *, framing=False):
        require_lesson_update = lesson_update_required(role, memory=config.lesson_memory,
            history=history, lessons=memory.snapshot())
        protocol = {'supervisor_strategy': config.supervisor_strategy, 'framing': framing}
        instructions = prompts.instructions_for(role, problem, **protocol)
        from .reasoning import instructions as contract_instructions
        instructions += contract_instructions(role, memory=config.lesson_memory,
            require_lesson_update=require_lesson_update, **protocol)
        tools = [] if framing else model_tools.tools_for(role, config, problem,
            require_lesson_update=require_lesson_update)
        schemas = {tool["function"]["name"]: tool["function"]["parameters"] for tool in tools}
        messages = [{"role": "system", "content": instructions},
                    {"role": "user", "content": context(role, framing=framing)}]
        browser_calls = other_calls = 0
        seen_calls = {}
        pending_invalid = None
        turns = config.max_turns_without_trial if role == "researcher" else config.review_tool_calls + 1
        for _ in range(turns):
            try:
                message = await model_call(role, messages, tools, framing=framing)
            except StopRun as stop:
                details = stop.details
                if (role != 'researcher' and pending_invalid is not None
                        and str(stop) == 'deadline' and details.get('reason') == 'deadline_admission'
                        and details.get('role') == role):
                    journal.emit('contract_abandoned', role=role, reason='deadline_admission',
                        **pending_invalid,
                        remaining_seconds=details.get('remaining_seconds'),
                        required_seconds=details.get('required_seconds'))
                raise
            messages.append(message)
            calls = message.get("tool_calls") or []
            if not calls:
                if role != "researcher":
                    contract = None
                    try:
                        contract = parse_contract(message.get("content"), allow_wrapper=True)
                        input_errors = schema_errors(contract, request_contract_schema(role, config.lesson_memory, **protocol), f'{role} request')
                        if input_errors:
                            raise ValueError(' '.join(input_errors))
                        contract = resolve_contract_evidence(contract, history)
                        errors = validate_contract(contract, role, history,
                            has_feedback=state.feedback is not None, memory=config.lesson_memory, **protocol)
                        if not errors:
                            contract = ground_accepted(contract, role, framing=framing)
                    except (ValueError, TypeError) as error:
                        errors = [str(error)]
                    journal.emit(role + "_contract", after_trial=summary["trials"],
                                 stage="framing" if framing else "review",
                                 contract=contract, valid=not errors, errors=errors)
                    if errors:
                        pending_invalid = {'after_trial': summary['trials'],
                            'stage': 'framing' if framing else 'review',
                            'contract': contract, 'errors': errors}
                        # The review has finished gathering evidence. Repairs
                        # only need the recorded measurements and format limits.
                        tools, schemas = [], {}
                        messages.append({"role": "user", "content":
                            "Correct the contract using the evidence already supplied. Return only the JSON object, "
                            "without a preamble or code fence. " + " ".join(errors)})
                        continue
                    pending_invalid = None
                    accept_lessons(contract)
                    return contract
                messages.append({"role": "user", "content": "Choose the next experiment with run_analysis."})
                continue
            # Multiple classifier calls would change review cadence. Reject the entire
            # response rather than silently executing an unreviewed batch.
            multiple_trials = sum(c.get("function", {}).get("name") == "run_analysis" for c in calls) > 1
            for call in calls:
                state.check()
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
                        intent = resolve_contract_evidence(args.pop("intent", None), history)
                        errors = validate_contract(intent, "researcher", history,
                            has_feedback=state.feedback is not None, memory=config.lesson_memory,
                            require_lesson_update=require_lesson_update)
                        if not errors:
                            intent = ground_accepted(intent, "researcher", require_lesson_update=require_lesson_update)
                        if errors:
                            journal.emit("decision_contract", trial_id=summary["trials"] + 1,
                                         contract=intent, valid=False, errors=errors)
                            contract_recorded = True
                            raise ValueError("Correct the decision contract: " + " ".join(errors))
                        from .diagnostics import experiment_diagnostic
                        diagnostic = experiment_diagnostic(args, problem=problem, project=project,
                                                           seed=config.training_seed, history=history)
                        equivalent = diagnostic['equivalent_trial_ids']
                        required = required_start_seconds(config, role='trial', history=history,
                            call_durations=state.call_durations, model=args.get('model'))
                        available = state.remaining()
                        skip_fit = not equivalent and available < required
                        journal.emit("decision_contract", trial_id=None if equivalent or skip_fit else summary["trials"] + 1,
                                     contract=intent, valid=True, errors=[], executed=not bool(equivalent or skip_fit),
                                     not_executed_reason='deadline_admission' if skip_fit else 'equivalent' if equivalent else None)
                        contract_recorded = True
                        if skip_fit:
                            journal.emit('trial_skipped', reason='deadline_admission', config=args,
                                         remaining_seconds=max(0, available), required_seconds=required)
                            raise StopRun('deadline')
                        if equivalent:
                            reuse_feedback['count'] += 1
                            reuse_feedback['latest'] = {'config': args, 'matched_trial_ids': equivalent}
                            prior = next(row for row in history if row['trial_id'] == equivalent[0])
                            result = {'status': 'reused', 'matched_trial_ids': equivalent,
                                      'observation': compact_result(prior),
                                      'message': 'This effective configuration and seed already completed. No fit or trial slot was used. Choose a different experiment.'}
                            journal.emit('experiment_reused', matched_trial_ids=equivalent,
                                         config=args, result=result)
                            messages.append({'role': 'tool', 'tool_call_id': call.get('id', ''),
                                             'content': json.dumps(result, allow_nan=False)})
                            continue
                        accept_lessons(intent)
                        return await trial_executor.execute(args, diagnostic, intent=intent, message=message)
                    if name.startswith("literature_"):
                        if browser_calls >= config.literature_calls_per_review:
                            raise ValueError("Per-review literature cap reached")
                        browser_calls += 1
                        if literature is None:
                            from .literature import LiteratureClient
                            # Default client created per call to keep ownership local.
                            client = LiteratureClient()
                        else:
                            client = literature
                        limit = min(state.remaining(), config.literature_timeout_seconds)
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
                except StopRun:
                    raise
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
        state.check()
        if config.review_every:
            state.initial_framing = state.feedback = await phase("supervisor", framing=True)
            journal.emit("framing", after_trial=0, feedback=state.feedback["summary"], contract=state.feedback)
        while True:
            state.check()
            await phase("researcher")
            state.check()  # No treatment calls if a safeguard/deadline precludes another trial.
            if config.review_every and summary["trials"] % config.review_every == 0:
                state.feedback = await phase("supervisor")
                journal.emit("review", after_trial=summary["trials"],
                             feedback=state.feedback["summary"], contract=state.feedback)
            if config.reflection:
                state.reflection = await phase("reflection")
                journal.emit("reflection", after_trial=summary["trials"],
                             reflection=state.reflection["summary"], contract=state.reflection)
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
        summary.update(stop_reason=stop_reason, elapsed_seconds=state.clock() - state.started,
                       accounting=accounting.snapshot())
        journal.emit("run_stopped", summary=summary)
        atomic_json(run_dir / "summary.json", summary)
    return summary
