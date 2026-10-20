"""Sequential, randomized matched-repeat scheduling and frozen provenance."""
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import random

from .config import CONDITIONS
from .controller import run_one
from .events import atomic_json, utc_now


def provenance(data_dir):
    sources = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
               for p in Path(__file__).parent.glob("*.py")}
    manifest = Path(data_dir) / "manifest.json"
    return {"python": platform.python_version(), "platform": platform.platform(),
        "dependencies": {name: version(name) for name in ("numpy", "scikit-learn", "httpx", "joblib")},
        "source_sha256": sources,
        "data_manifest": json.loads(manifest.read_text()) if manifest.exists() else None}


async def run_suite(config, data_dir, output, *, repeats, deadline, reserve_seconds,
                    model_factory, runner=run_one, order_seed=2026, provider_metadata=None):
    if deadline.tzinfo is None:
        raise ValueError("deadline must include a UTC offset")
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be a positive integer")
    if not math.isfinite(reserve_seconds) or reserve_seconds <= 0:
        raise ValueError("reserve_seconds must be positive")
    search_deadline = deadline.timestamp() - reserve_seconds
    required = repeats * len(CONDITIONS) * config.allowance_seconds
    if search_deadline - datetime.now(timezone.utc).timestamp() < required:
        raise ValueError("Study window cannot fit all equal allowances plus reporting reserve")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    rng = random.Random(order_seed)
    schedule = []
    for repeat in range(repeats):
        order = list(CONDITIONS)
        rng.shuffle(order)
        for condition in order:
            schedule.append({"condition": condition, "repeat": repeat,
                             "run_id": f"r{repeat:02d}-{condition}"})
    manifest = {"created_at": utc_now(), "config": config.to_dict(), "repeats": repeats,
        "schedule": schedule, "order_seed": order_seed, "deadline": deadline.isoformat(),
        "reserve_seconds": reserve_seconds, "provenance": provenance(data_dir),
        "provider_metadata": provider_metadata}
    atomic_json(output / "suite.json", manifest)
    summaries = []
    for entry in schedule:
        run_config = config.for_run(entry["condition"], entry["repeat"])
        run_dir = output / "runs" / entry["run_id"]
        if search_deadline - datetime.now(timezone.utc).timestamp() < config.allowance_seconds:
            # Keep planned runs visible in the all-runs denominator.
            run_dir.mkdir(parents=True)
            summary = {"condition": run_config.condition, "repeat": run_config.repeat,
                "allowance_seconds": run_config.allowance_seconds, "config": run_config.to_dict(),
                "trials": 0, "best": None, "milestone": None, "stretch": None,
                "elapsed_seconds": 0, "training_seconds": 0, "stop_reason": "not_started_study_deadline",
                "accounting": {"known_cost": 0, "cost_complete": True, "input_tokens": 0,
                    "output_tokens": 0, "token_usage_complete": True}}
            atomic_json(run_dir / "summary.json", summary)
        else:
            model = model_factory(run_config)
            try:
                kwargs = {"provider_metadata": provider_metadata} if provider_metadata is not None else {}
                summary = await runner(run_config, data_dir, run_dir, model, **kwargs)
            finally:
                if hasattr(model, "aclose"):
                    await model.aclose()
        summaries.append(summary)
    atomic_json(output / "search-complete.json", {"completed_at": utc_now(),
        "runs": len(summaries), "stop_reasons": [s["stop_reason"] for s in summaries]})
    return summaries
