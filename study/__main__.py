"""Run `python -m study --help` for the preparation-to-report workflow."""
import argparse
import asyncio
from contextlib import nullcontext
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import sys
import time
import tempfile

from .config import CONDITIONS, StudyConfig
from .controller import recover_run, run_one
from .events import atomic_json, utc_now
from .suite import provenance, run_suite


def load_config(path):
    return StudyConfig(**json.loads(Path(path).read_text())) if path else StudyConfig()


def live_model(config):
    from .provider import OpenRouter
    if not config.model or not config.provider:
        raise ValueError("Live runs require explicit model and provider in the config")
    return OpenRouter(config.model, config.provider, temperature=config.temperature,
                      max_tokens=config.max_tokens)


def run_directories(root):
    root = Path(root)
    return [root] if (root / "summary.json").exists() else sorted(
        path.parent for path in (root / "runs").glob("*/summary.json"))


def selected_artifacts(summary):
    """Generic named targets, with historical milestone/stretch support."""
    targets = summary.get("target_selections")
    selected = {"best": summary.get("best")}
    selected.update(targets if isinstance(targets, dict) else {
        name: summary.get(name) for name in ("milestone", "stretch")})
    return {name: item for name, item in selected.items() if item is not None}


def require_successful_runs(summaries):
    """Expected limits are successful only when search produced a valid model."""
    failures = []
    for summary in summaries:
        reason = summary.get("stop_reason", "missing")
        if reason not in {"deadline", "trial_cap", "dollar_cap"} or not summary.get("best"):
            identity = f"{summary.get('condition', 'unknown')}/r{summary.get('repeat', 0)}"
            failures.append(f"{identity}: {reason}" +
                            (" (no valid model)" if not summary.get("best") else ""))
    if failures:
        raise RuntimeError("Search failed; artifacts retained: " + "; ".join(failures))


def preflight_problem(problem_path, data_dir):
    """Validate scientific identity before constructing a provider or using a key."""
    from .problem import load_problem, problem_from_data, assert_problem_matches
    problem = load_problem(problem_path) if problem_path else problem_from_data(data_dir)
    if problem is not None:
        assert_problem_matches(data_dir, problem)
    else:
        # Legacy datasets still receive data integrity checks before network work.
        from .science import _hash_file
        manifest = json.loads((Path(data_dir) / "manifest.json").read_text())
        for name, partition in manifest["partitions"].items():
            if _hash_file(Path(data_dir) / f"{name}.npz") != partition["sha256"]:
                raise ValueError(f"{name} partition fingerprint mismatch")
    return problem


def evaluate(data_dir, root):
    from .science import evaluate_selected
    root = Path(root)
    begin = time.monotonic()
    directories = run_directories(root)
    if not directories:
        raise ValueError("No frozen runs to evaluate; recover interrupted runs first")
    selections = {}
    selection_names = {}
    for run_dir in directories:
        summary = json.loads((run_dir / "summary.json").read_text())
        selected = selected_artifacts(summary)
        selection_names[run_dir] = list(selected)
        for name, item in selected.items():
            selections[f"{run_dir.name}/{name}"] = item
    # A suite shares one cache, including identical artifacts selected by different
    # conditions. Per-run views contain no new scoring, just references to it.
    cache_dir = root / "evaluation"
    results = evaluate_selected(Path(data_dir), cache_dir, selections)
    for run_dir in directories:
        selected = {name: results[f"{run_dir.name}/{name}"] for name in
                    selection_names[run_dir] if f"{run_dir.name}/{name}" in results}
        atomic_json(run_dir / "test-results.json", {"selections": selected,
            "artifacts": {item["artifact_hash"]: item for item in selected.values()}})
    previous = json.loads((root / "postrun.json").read_text()) if (root / "postrun.json").exists() else {}
    atomic_json(root / "postrun.json", previous | {"evaluation_seconds": time.monotonic() - begin,
        "evaluation_finished_at": utc_now(), "model_cost": 0, "note": "Local held-out scoring only; no LLM judge."})
    failures = [name for name, result in results.items() if result.get("status") != "completed"]
    if not selections or failures:
        raise RuntimeError("Held-out evaluation failed; results retained: " +
                           (", ".join(failures) if failures else "no selected models"))


async def finish_before_deadline(data_dir, output, deadline, *, validation_only=False):
    """Killable postrun phases; reserve cannot extend the study's hard deadline."""
    from .science import THREAD_ENV
    statuses = {}
    for command in ("evaluate", "report"):
        if command == "evaluate" and validation_only:
            statuses[command] = "skipped_validation_only"
            continue
        remaining = deadline.timestamp() - datetime.now(timezone.utc).timestamp()
        limit = remaining * .7 if command == "evaluate" else remaining
        if limit <= 0:
            statuses[command] = "not_started_deadline"
            continue
        args = [sys.executable, "-m", "study", command, "--output", str(output)]
        if command == "evaluate":
            args.extend(["--data", str(data_dir)])
        process = await asyncio.create_subprocess_exec(*args, start_new_session=True,
            env={"PATH": os.defpath, "LANG": "C.UTF-8", **THREAD_ENV},
            cwd=Path(__file__).resolve().parent.parent)
        try:
            await asyncio.wait_for(process.wait(), timeout=limit)
            statuses[command] = "completed" if process.returncode == 0 else "failed"
        except (TimeoutError, asyncio.CancelledError):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()
            statuses[command] = "timeout"
            if asyncio.current_task().cancelling():
                raise
    atomic_json(Path(output) / "completion.json", {"finished_at": utc_now(), "postrun": statuses})
    if any(status not in ("completed", "skipped_validation_only") for status in statuses.values()):
        raise RuntimeError(f"Postrun failed; see {Path(output) / 'completion.json'}: {statuses}")


async def dispatch(args):
    from .progress import ConsoleProgress
    if args.command == "watch":
        from .findings import watch
        await watch(args.output, interval=args.interval, once=args.once, animate=not args.no_animation)
        return
    progress = None if getattr(args, "quiet", False) else ConsoleProgress(
        verbose=getattr(args, "verbose", False), summary_interval=getattr(args, "summary_interval", 15),
        animate=not getattr(args, "no_animation", False))
    async with progress if progress is not None else nullcontext():
        await _dispatch(args, progress)


async def _dispatch(args, progress):
    from .science import prepare_dataset, fixed_reference
    problem_path = getattr(args, "problem", None)
    if args.command == "init-problem":
        template = Path(__file__).parent / "problems" / f"{args.template}.yaml"
        # Exclusive creation preserves an existing user definition.
        with args.output.open("x") as handle:
            handle.write(template.read_text())
        print(f"Created {args.output}. Edit dataset paths relative to that file, then run validate.")
    elif args.command == "validate":
        from .problem import load_problem
        from .tasks import get_adapter
        problem = load_problem(args.problem)
        with tempfile.TemporaryDirectory(prefix="nightagent-validate-") as temporary:
            prepared = Path(temporary) / "data"
            prepare_dataset(prepared, problem=problem)
            description = get_adapter(problem).describe(prepared)
        print(json.dumps({"valid": True, "problem_hash": problem.fingerprint,
            "resolved_problem": problem.to_dict(), "project": description}, indent=2))
    elif args.command == "prepare":
        if problem_path:
            if getattr(args, "seed", None) is not None:
                raise ValueError("Set split seed in the problem profile; --seed is only for legacy --csv/--synthetic")
            from .problem import load_problem
            manifest = prepare_dataset(args.output, problem=load_problem(problem_path))
        else:
            seed = args.seed if args.seed is not None else 42
            manifest = prepare_dataset(args.output, csv_path=args.csv, synthetic=args.synthetic, seed=seed)
        print(f"Prepared {manifest['dataset']} in {args.output}; fingerprint {manifest['data_fingerprint']}")
    elif args.command == "recover":
        summary = recover_run(args.output)
        print(f"Frozen {args.output}: {summary['stop_reason']}")
    elif args.command == "evaluate":
        evaluate(args.data, args.output)
        print(f"Held-out results saved under {args.output}")
    elif args.command == "report":
        from .report import generate_report
        begin = time.monotonic()
        path = generate_report(args.output)
        previous = json.loads((args.output / "postrun.json").read_text()) if (args.output / "postrun.json").exists() else {}
        atomic_json(args.output / "postrun.json", previous | {"reporting_seconds": time.monotonic() - begin})
        print(path)
    elif args.command == "reference":
        preflight_problem(problem_path, args.data)
        result = await fixed_reference(args.data, args.output, seed=args.seed, timeout=args.timeout)
        print(json.dumps(result, indent=2))
        if result.get("status") != "completed":
            raise RuntimeError(f"Reference failed: {result.get('status')}; see {args.output}")
    elif args.command == "smoke":
        from .fake import FakeLiterature, FakeModel
        from .report import generate_report
        # All model and literature calls are local fixtures; classifiers are real.
        problem = None
        options = None
        if problem_path:
            from .problem import load_problem
            from .tasks import get_adapter
            problem = load_problem(problem_path)
            options = [get_adapter(problem).reference_config]
        args.output.mkdir(parents=True, exist_ok=False)
        data_dir = args.output / "data"
        if problem:
            prepare_dataset(data_dir, problem=problem)
        else:
            prepare_dataset(data_dir, synthetic=True)
        summaries = []
        for condition in CONDITIONS:
            config = StudyConfig(condition=condition, model="offline-script", provider="offline",
                allowance_seconds=60, trial_cap=4, trial_timeout_seconds=15,
                lesson_memory=bool(getattr(args, "lesson_memory", False)))
            summaries.append(await run_one(config, data_dir, args.output / "runs" / condition,
                FakeModel(options=options), literature=FakeLiterature(), problem=problem, progress=progress))
        atomic_json(args.output / "smoke.json", {"offline": True, "provenance": provenance(data_dir),
                    "note": "Scripted model and fixture literature; workflow verification, not agent comparison evidence."})
        evaluate(data_dir, args.output)
        print(generate_report(args.output))
        if any(s["stop_reason"] != "trial_cap" or s["best"] is None for s in summaries):
            raise RuntimeError("Offline smoke did not complete every condition")
    elif args.command in ("run", "suite"):
        config = load_config(args.config)
        if getattr(args, "lesson_memory", None) is not None:
            config = replace(config, lesson_memory=args.lesson_memory)
        if getattr(args, "max_cores", None) is not None:
            config = replace(config, max_cores=args.max_cores)
        problem = preflight_problem(problem_path, args.data)
        if getattr(args, "env_file", None):
            from .credentials import load_openrouter_env
            load_openrouter_env(args.env_file)
        # Validate provider/key before allocating a suite/run directory.
        initial = live_model(config)
        try:
            provider_metadata = await initial.describe()
            provider_metadata["runtime"] = provenance(args.data)
        finally:
            await initial.aclose()
        if args.command == "run":
            config = replace(config, condition=args.condition or config.condition)
            model = live_model(config)
            try:
                summary = await run_one(config, args.data, args.output, model,
                                        provider_metadata=provider_metadata, problem=problem, progress=progress)
            finally:
                await model.aclose()
            # Render even failed searches, after the model is closed and outside
            # the search allowance. Reporting reads artifacts; it never scores test data.
            from .report import generate_report
            report_path = generate_report(args.output)
            print(json.dumps({k: summary[k] for k in ("condition", "trials", "stop_reason", "accounting")}
                             | {"report": str(report_path.resolve())}, indent=2))
            require_successful_runs([summary])
        else:
            deadline = datetime.fromisoformat(args.deadline)
            summaries = await run_suite(config, args.data, args.output, repeats=args.repeats, deadline=deadline,
                reserve_seconds=args.reserve_seconds, order_seed=args.order_seed, model_factory=live_model,
                provider_metadata=provider_metadata, problem=problem, progress=progress,
                validation_only=getattr(args, 'validation_only', False))
            await finish_before_deadline(args.data, args.output, deadline,
                validation_only=getattr(args, 'validation_only', False))
            require_successful_runs(summaries)


def main():
    parser = argparse.ArgumentParser(description="Controlled NightAgent wall-time study via OpenRouter.")
    sub = parser.add_subparsers(dest="command", required=True)
    watch_parser = sub.add_parser("watch", help="Read-only live findings for an existing single run")
    watch_parser.add_argument("--output", type=Path, required=True, help="Run directory containing events.jsonl")
    watch_parser.add_argument("--interval", type=float, default=15, help="Seconds between changed summaries (default 15)")
    watch_parser.add_argument("--once", action="store_true", help="Print one snapshot and exit")
    watch_parser.add_argument("--no-animation", action="store_true", help="Disable the interactive status line")
    init = sub.add_parser("init-problem", help="Create an editable problem profile from an example")
    init.add_argument("--template", choices=("magic", "classification", "mnist", "regression"), default="classification")
    init.add_argument("--output", type=Path, required=True)
    validate = sub.add_parser("validate", help="Validate a problem and its data without fitting or calling a model")
    validate.add_argument("--problem", type=Path, required=True)
    prepare = sub.add_parser("prepare", help="Freeze a problem's dataset and evaluation partitions")
    source = prepare.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", type=Path)
    source.add_argument("--synthetic", action="store_true")
    source.add_argument("--problem", type=Path)
    prepare.add_argument("--seed", type=int, help="Legacy data split seed (default 42); profiles contain their own seed")
    prepare.add_argument("--output", type=Path, required=True)
    for command in ("run", "suite"):
        p = sub.add_parser(command, help="Paid OpenRouter experiment" if command == "run" else "Five-condition comparison with optional automatic concurrency")
        p.add_argument("--config", type=Path, required=True)
        p.add_argument("--data", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True)
        p.add_argument("--problem", type=Path, help="Problem profile; defaults to the frozen prepared definition")
        p.add_argument("--env-file", type=Path, help="Read OpenRouter credentials from this env file (no shell execution)")
        p.add_argument("--summary-interval", type=float, default=15,
                       help="Seconds between findings summaries (default 15; 0 disables summaries)")
        p.add_argument("--lesson-memory", action=argparse.BooleanOptionalAction, default=None,
                       help="Enable bounded lessons within each run; a separately recorded experimental variant")
        p.add_argument("--max-cores", type=int, help="Maximum local training threads; automatically balances independent suite runs")
        p.add_argument("--no-animation", action="store_true", help="Disable the interactive status line")
        display = p.add_mutually_exclusive_group()
        display.add_argument("--verbose", action="store_true", help="Show full model text and tool results live")
        display.add_argument("--quiet", action="store_true", help="Suppress live progress; retain logs and final summary")
        if command == "run":
            p.add_argument("--condition", choices=CONDITIONS)
        else:
            p.add_argument("--validation-only", action="store_true",
                           help="Pilot all strategies and generate a report without held-out test scoring")
            p.add_argument("--repeats", type=int, default=5)
            p.add_argument("--deadline", required=True, help="Hard study deadline with timezone, e.g. 2026-10-21T08:00:00-04:00")
            p.add_argument("--reserve-seconds", type=float, default=3600)
            p.add_argument("--order-seed", type=int, default=2026)
    reference = sub.add_parser("reference", help="Fixed classifier reference outside the five conditions")
    reference.add_argument("--data", type=Path, required=True)
    reference.add_argument("--output", type=Path, required=True)
    reference.add_argument("--seed", type=int, default=42)
    reference.add_argument("--timeout", type=float, default=60)
    reference.add_argument("--problem", type=Path)
    for command in ("smoke", "evaluate", "report", "recover"):
        p = sub.add_parser(command)
        p.add_argument("--output", type=Path, required=True)
        if command == "evaluate":
            p.add_argument("--data", type=Path, required=True)
        if command == "smoke":
            p.add_argument("--lesson-memory", action="store_true", help="Exercise run-local lessons offline")
            p.add_argument("--problem", type=Path, help="Optional profile for a scripted all-condition smoke run")
            display = p.add_mutually_exclusive_group()
            display.add_argument("--verbose", action="store_true")
            display.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(dispatch(args))
    except KeyboardInterrupt:
        parser.exit(130, "Interrupted.\n")
    except (ValueError, FileExistsError, FileNotFoundError, RuntimeError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
