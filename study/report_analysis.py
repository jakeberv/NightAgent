"""Offline role accounting and conservative matched-repeat analysis."""
from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
import json
import math
import re
from statistics import mean, stdev


def number(value):
    return float(value) if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def role_metrics(events):
    grouped = defaultdict(list)
    for event in events:
        if event.get("type") in ("model_call", "model_call_started"):
            grouped[str(event.get("role") or "unknown")].append(event)
    result = {}
    for role, records in grouped.items():
        calls = [e for e in records if e["type"] == "model_call"]
        starts = sum(e["type"] == "model_call_started" for e in records)
        attempts = max(starts, len(calls))
        unfinished = max(0, starts - len(calls))
        statuses = Counter(e.get("status", "unknown") for e in calls)
        complete_trace = starts == len(calls) and bool(calls)
        values = {}
        usages = [e.get("usage") if isinstance(e.get("usage"), dict) else {} for e in calls]
        for field, raw, detail in [("known_cost", "cost", None), ("input_tokens", "prompt_tokens", None),
                ("output_tokens", "completion_tokens", None),
                ("cached_tokens", "cached_tokens", "prompt_tokens_details"),
                ("reasoning_tokens", "reasoning_tokens", "completion_tokens_details")]:
            measurements = [number((usage.get(detail) or {}).get(raw) if detail else usage.get(raw))
                            for usage in usages]
            known = [v for v in measurements if v is not None]
            values[field] = sum(known) if known else None
            values[field + "_complete"] = complete_trace and len(known) == attempts
        durations = [number(e.get("duration_seconds")) for e in calls]
        known_times = [v for v in durations if v is not None]
        failed = statuses["failed"] + statuses["timeout"]
        unknown = len(calls) - sum(statuses[s] for s in ("completed", "failed", "timeout", "cancelled"))
        tokens_complete = values["input_tokens_complete"] and values["output_tokens_complete"]
        result[role] = {**values, "attempts": attempts, "completed": statuses["completed"],
            "failed": failed, "cancelled": statuses["cancelled"], "unfinished": unfinished,
            "unknown_status": unknown, "status_complete": not (unfinished or unknown),
            "failure_fraction": (failed + statuses["cancelled"]) / attempts if not (unfinished or unknown) else None,
            "retry_attempts": sum(type(e.get("attempt")) is int and e["attempt"] > 0 for e in calls),
            "model_seconds": sum(known_times) if known_times else None,
            "model_seconds_complete": complete_trace and len(known_times) == attempts,
            "cost_complete": values["known_cost_complete"],
            "total_cost": values["known_cost"] if values["known_cost_complete"] else None,
            "token_usage_complete": tokens_complete,
            "total_tokens": values["input_tokens"] + values["output_tokens"] if tokens_complete else None}
    return result


def recommendation_uptake(events, trials, valid_trials):
    records = [event for event in events if event.get("type") == "decision_contract"]
    counts = dict.fromkeys(("followed", "modified", "rejected", "not_applicable", "unknown", "invalid"), 0)
    all_trials = {str(t["trial_id"]): t for t in trials}
    scores = {str(t["trial_id"]): t["score"] for t in valid_trials}
    outcomes = []
    reused = 0
    for event in records:
        if event.get("executed") is False:
            reused += 1
            continue
        if event.get("valid") is not True:
            counts["invalid"] += 1
            continue
        contract = event.get("contract") or {}
        response = contract.get("supervisor_response", "unknown")
        if response not in ("followed", "modified", "rejected", "not_applicable"):
            response = "unknown"
        counts[response] += 1
        trial_id = str(event.get("trial_id"))
        baseline = str(contract.get("baseline_trial_id"))
        before, after = scores.get(baseline), scores.get(trial_id)
        outcomes.append({"trial_id": trial_id, "baseline_trial_id": contract.get("baseline_trial_id"),
            "supervisor_response": response, "response_reason": contract.get("response_reason"),
            "trial_status": all_trials.get(trial_id, {}).get("status", "unknown"),
            "baseline_score": before, "trial_score": after,
            "validation_delta": after - before if before is not None and after is not None else None})
    applicable = sum(counts[s] for s in ("followed", "modified", "rejected"))
    return {**counts, "recorded_contracts": len(records), "reused_proposals": reused, "applicable": applicable,
            "followed_fraction": counts["followed"] / applicable if applicable else None,
            "outcomes": outcomes}


def literature_coverage(events, config=None, condition=None, *, events_available=True):
    """Describe recorded retrieval evidence, without inferring reasoning use.

    Attempts count tool-call records (including rejected requests), not network
    requests. Missing event logs are unknown, rather than an unexercised tool.
    """
    condition = (config or {}).get("condition", condition)
    enabled = condition == "periodic_reflection_literature" if condition else None
    names = {"literature_search", "literature_fetch"}
    offered = {tool.get("function", {}).get("name") for event in events
               if event.get("type") == "model_call_started"
               for tool in event.get("tools", []) if isinstance(tool, dict)} & names
    counts = dict.fromkeys(("search_attempts", "search_successes", "search_results",
                           "fetch_attempts", "fetch_successes", "source_passages_retrieved"), 0)
    source_urls, feedback_urls = set(), set()
    feedback_records = 0

    def present(value):
        return isinstance(value, str) and bool(value.strip())

    def urls(value):
        if isinstance(value, dict):
            return set().union(*(urls(item) for item in value.values())) if value else set()
        if isinstance(value, list):
            return set().union(*(urls(item) for item in value)) if value else set()
        if not isinstance(value, str):
            return set()
        return {url.rstrip(".,;:!?)])}") for url in re.findall(r'https?://[^\s<>"\x27]+', value)}

    for event in events:
        name = event.get("name")
        if event.get("type") == "tool_call" and name in names:
            operation = "search" if name == "literature_search" else "fetch"
            counts[operation + "_attempts"] += 1
            result = event.get("result")
            if not isinstance(result, dict) or "error" in result:
                continue
            if operation == "search":
                results = result.get("results")
                if not isinstance(results, list):
                    continue
                counts["search_successes"] += 1
                for item in results:
                    if not isinstance(item, dict):
                        continue
                    if any(present(item.get(key)) for key in ("title", "doi", "url", "passage")):
                        counts["search_results"] += 1
                    counts["source_passages_retrieved"] += present(item.get("passage"))
                    source_urls.update(urls(item.get("url")))
            elif isinstance(result.get("text"), str):
                counts["fetch_successes"] += 1
                counts["source_passages_retrieved"] += present(result["text"])
                source_urls.update(urls(result.get("url")) | urls(result.get("final_url")))
        elif event.get("type") == "review":
            feedback_records += 1
            # Match explicit source URLs in accepted feedback only, not tool
            # messages, prompts, or unaccepted model drafts.
            feedback_urls.update((urls(event.get("feedback")) | urls(event.get("contract"))) & source_urls)
    attempts = counts["search_attempts"] + counts["fetch_attempts"]
    state = ("unknown" if not events_available else
             "passage_retrieved" if counts["source_passages_retrieved"] else
             "attempted_without_passage" if attempts else
             "unexercised" if enabled or offered else "not_enabled")
    return {"enabled": enabled, "tools_offered": sorted(offered) if events_available else None,
            "events_available": events_available, "state": state,
            **{key: value if events_available else None for key, value in counts.items()},
            "source_urls": sorted(source_urls) if events_available else None,
            "feedback_records": feedback_records if events_available else None,
            "feedback_source_urls": sorted(feedback_urls) if events_available else None}


def config_stratum(row):
    # Retain every other frozen config key, including protocol, memory, and limits.
    return {key: value for key, value in (row.get("config") or {}).items()
            if key not in ("condition", "repeat", "training_seed")}


def assign_analysis_groups(runs):
    """Separate protocol and memory variants while preserving legacy summaries."""
    def variant(row):
        return json.dumps({key: (row.get("config") or {}).get(key)
                           for key in ("decision_protocol", "reasoning_policy", "supervisor_policy",
                                       "lesson_memory", "memory_limit")}, sort_keys=True)
    variants = defaultdict(set)
    for row in runs:
        variants[row["condition"]].add(variant(row))
    for row in runs:
        configs = sorted(variants[row["condition"]])
        row["analysis_group"] = row["condition"]
        if len(configs) > 1:
            index = configs.index(variant(row)) + 1
            row["analysis_group"] += f" [configuration {index}]"


def delta_summary(values):
    n = len(values)
    average = mean(values) if values else None
    interval = None
    sd = stdev(values) if n > 1 else None
    if n > 1:
        from scipy.stats import t
        half = float(t.ppf(.975, n - 1)) * sd / math.sqrt(n)
        interval = [average - half, average + half]
    return {"n": n, "mean_delta": average, "sd_delta": sd, "ci95": interval}


def paired_comparisons(runs, warnings):
    groups = defaultdict(list)
    excluded = []
    for row in runs:
        config = row.get("config") or {}
        seed, repeat = config.get("training_seed"), row.get("repeat")
        if (not row.get("problem_hash") or not row.get("data_fingerprint") or not config
                or type(seed) is not int or type(repeat) is not int
                or config.get("repeat", repeat) != repeat
                or config.get("condition", row["condition"]) != row["condition"]
                or row.get("allowance_seconds") is None):
            excluded.append(row["run_id"])
            continue
        key = json.dumps({"config": config_stratum(row), "problem_hash": row["problem_hash"],
                          "problem": row.get("problem"), "data_fingerprint": row["data_fingerprint"],
                          "objective": row["objective"], "allowance_seconds": row["allowance_seconds"],
                          "target_definitions": row.get("target_definitions")}, sort_keys=True)
        groups[key].append(row)
    if excluded:
        warnings.append("Matched comparisons exclude runs with unknown or inconsistent frozen identity, seed, repeat, "
                        "or configuration: " + ", ".join(excluded) + ".")
    result = []
    for key, rows in sorted(groups.items()):
        conditions = sorted({r["condition"] for r in rows}, key=lambda c: (c != "researcher_alone", c))
        units = defaultdict(list)
        for row in rows:
            units[(row["condition"], row["repeat"], row["config"]["training_seed"])].append(row)
        for (condition, repeat, seed), duplicates in units.items():
            if len(duplicates) > 1:
                warnings.append(f"Duplicate matched unit for {condition}, repeat {repeat}, seed {seed}; "
                                "these runs are excluded from pairing.")
        for a, b in combinations(conditions, 2):
            a_rows, b_rows = [r for r in rows if r["condition"] == a], [r for r in rows if r["condition"] == b]
            pairs = []
            for left in a_rows:
                unit = left["repeat"], left["config"]["training_seed"]
                right = units.get((b, *unit), [])
                if len(units[(a, *unit)]) == len(right) == 1:
                    pairs.append((left, right[0]))
            metrics = {}
            for field in ("best_score", "total_cost", "total_tokens", "model_seconds", "training_seconds", "elapsed_seconds"):
                def measurement(row):
                    if field in ("model_seconds", "training_seconds") and not row.get(field + "_complete"):
                        return None
                    return row.get(field)
                differences = [measurement(right) - measurement(left) for left, right in pairs
                               if measurement(left) is not None and measurement(right) is not None]
                metrics[field] = delta_summary(differences)
            target_deltas = {}
            for target in dict.fromkeys(name for r in rows for name in r["targets"]):
                target_deltas[target] = {
                    "attainment": delta_summary([float(right["targets"][target]["reached"]) - float(left["targets"][target]["reached"])
                         for left, right in pairs if target in left["targets"] and target in right["targets"]]),
                    "crossing_seconds": delta_summary([right["targets"][target]["seconds"] - left["targets"][target]["seconds"]
                         for left, right in pairs if left["targets"].get(target, {}).get("seconds") is not None
                         and right["targets"].get(target, {}).get("seconds") is not None])}
            result.append({"condition_a": a, "condition_b": b, **json.loads(key),
                "runs_a": len(a_rows), "runs_b": len(b_rows), "matched_pairs": len(pairs),
                "unmatched_runs_a": len(a_rows) - len(pairs), "unmatched_runs_b": len(b_rows) - len(pairs),
                "no_valid_model_a": sum(r["best_score"] is None for r in a_rows),
                "no_valid_model_b": sum(r["best_score"] is None for r in b_rows),
                "stop_reasons_a": dict(Counter(r["stop_reason"] for r in a_rows)),
                "stop_reasons_b": dict(Counter(r["stop_reason"] for r in b_rows)),
                "missing_score_pairs": len(pairs) - metrics["best_score"]["n"],
                "pair_ids": [{"run_a": left["run_id"], "run_b": right["run_id"],
                              "repeat": left["repeat"], "training_seed": left["config"]["training_seed"]}
                             for left, right in pairs], "metrics": metrics, "targets": target_deltas})
    if len({r["condition"] for r in runs}) > 1 and not any(c["matched_pairs"] for c in result):
        warnings.append("No unique matched condition pairs were found; configuration and seed differences are not pooled.")
    return result
