"""Randomized matched-repeat scheduling with optional bounded concurrency."""
import asyncio
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
import math
from pathlib import Path
import platform
import random

from .config import comparison_arms
from .controller import prepared_fingerprint, resolve_problem, run_one
from .selection import initial_summary
from .events import atomic_json, utc_now


def provenance(data_dir):
    sources = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
               for p in Path(__file__).parent.glob("*.py")}
    manifest = Path(data_dir) / "manifest.json"
    dependencies = {name: version(name) for name in ("numpy", "scikit-learn", "httpx", "joblib")}
    try:
        dependencies['torch'] = version('torch')
    except PackageNotFoundError:
        pass
    return {"python": platform.python_version(), "platform": platform.platform(),
        "dependencies": dependencies,
        "source_sha256": sources,
        "data_manifest": json.loads(manifest.read_text()) if manifest.exists() else None}


async def run_suite(config, data_dir, output, *, repeats, deadline, reserve_seconds,
                    model_factory, runner=run_one, order_seed=2026, provider_metadata=None, problem=None,
                    progress=None, validation_only=False):
    if deadline.tzinfo is None:
        raise ValueError("deadline must include a UTC offset")
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    # Seeds increase monotonically with repeat; validate the full range before
    # creating output or allowing any earlier repeat to spend its budget.
    config.for_run(config.condition, repeats - 1)
    if not math.isfinite(reserve_seconds) or reserve_seconds <= 0:
        raise ValueError("reserve_seconds must be positive")
    search_deadline = deadline.timestamp() - reserve_seconds
    resolved_problem = resolve_problem(config, data_dir, problem)
    from .controller import execution_config
    config = execution_config(config, resolved_problem)
    concurrent_runs = 2 if config.max_cores is not None else 1
    arms = comparison_arms(config)
    required = math.ceil(repeats * len(arms) / concurrent_runs) * config.allowance_seconds
    balanced_trials = None
    execution = {"concurrent_runs": concurrent_runs, "max_cores": 1, "policy": "sequential"}
    if config.max_cores is not None:
        from .resources import CorePool, BalancedTrials
        balanced_trials = BalancedTrials(CorePool(config.max_cores), device=config.device)
        execution.update(max_cores=balanced_trials.pool.limit, policy="automatic_shared_core_pool", device=config.device,
                         concurrent_gpu_fits=1 if config.device == 'mps' else 0)
    if search_deadline - datetime.now(timezone.utc).timestamp() < required:
        raise ValueError("Study window cannot fit all equal allowances plus reporting reserve")
    # Verify frozen science and partition hashes before constructing any provider.
    data_fingerprint = prepared_fingerprint(data_dir)
    from .problem import problem_from_data
    pass_problem = problem is not None or problem_from_data(data_dir) is not None
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    rng = random.Random(order_seed)
    schedule = []
    for repeat in range(repeats):
        order = list(arms)
        rng.shuffle(order)
        for arm in order:
            schedule.append({**arm, "repeat": repeat,
                             "run_id": f"r{repeat:02d}-{arm['arm']}"})
    manifest = {"created_at": utc_now(), "config": config.to_dict(), "repeats": repeats,
        "schedule": schedule, "order_seed": order_seed, "deadline": deadline.isoformat(),
        "reserve_seconds": reserve_seconds, "execution": execution, "provenance": provenance(data_dir),
        "postrun_policy": "validation_only" if validation_only else "heldout_and_report",
        "provider_metadata": provider_metadata, "problem": resolved_problem.to_dict(),
        "problem_hash": resolved_problem.fingerprint, "data_fingerprint": data_fingerprint,
        "objective": resolved_problem.objective,
        "target_definitions": resolved_problem.targets}
    atomic_json(output / "suite.json", manifest)
    summaries = [None] * len(schedule)
    async def execute_entry(index, entry):
        run_config = config.for_run(entry["condition"], entry["repeat"],
                                    supervisor_strategy=entry['supervisor_strategy'],
                                    lesson_memory=entry.get('lesson_memory'))
        run_dir = output / "runs" / entry["run_id"]
        if search_deadline - datetime.now(timezone.utc).timestamp() < config.allowance_seconds:
            # Keep planned runs visible in the all-runs denominator.
            run_dir.mkdir(parents=True)
            summary = initial_summary(run_config, resolved_problem, data_fingerprint)
            summary.update(elapsed_seconds=0, stop_reason="not_started_study_deadline",
                accounting={"known_cost": 0, "cost_complete": True, "input_tokens": 0,
                    "output_tokens": 0, "token_usage_complete": True})
            atomic_json(run_dir / "summary.json", summary)
        else:
            if pass_problem:
                resolve_problem(run_config, data_dir, resolved_problem)
            if prepared_fingerprint(data_dir) != data_fingerprint:
                raise ValueError("Prepared data fingerprint differs from frozen suite")
            model = model_factory(run_config)
            try:
                kwargs = {"provider_metadata": provider_metadata} if provider_metadata is not None else {}
                if balanced_trials is not None:
                    kwargs["trial_runner"] = balanced_trials
                if pass_problem:
                    kwargs["problem"] = resolved_problem
                if progress is not None:
                    kwargs["progress"] = progress
                summary = await runner(run_config, data_dir, run_dir, model, **kwargs)
            finally:
                if hasattr(model, "aclose"):
                    await model.aclose()
        summaries[index] = summary
    if concurrent_runs == 1:
        for index, entry in enumerate(schedule):
            await execute_entry(index, entry)
    else:
        queue = iter(enumerate(schedule))
        async def worker():
            for index, entry in queue:
                await execute_entry(index, entry)
        async with asyncio.TaskGroup() as group:
            for _ in range(concurrent_runs):
                group.create_task(worker())
    atomic_json(output / "search-complete.json", {"completed_at": utc_now(),
        "runs": len(summaries), "stop_reasons": [s["stop_reason"] for s in summaries]})
    return summaries
