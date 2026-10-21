"""Select measured validation results against frozen objectives and targets."""
import math


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
