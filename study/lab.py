"""Bounded, read-only presentation state from the runner's existing events."""
from collections import deque
from copy import deepcopy
import json
import math
import re


def excerpt(value, limit=240):
    from .progress import _safe
    if not isinstance(value, str):
        return ""
    # Prefer an explicitly titled rationale; otherwise show a labeled excerpt.
    match = re.search(r"(?im)^[ \t]*(?:#{1,6}[ \t]+|\*\*)rationale[ \t]*:?(?:\*\*)?[ \t]*\n", value)
    if match:
        value = value[match.end():].split("\n#", 1)[0]
    value = " ".join(_safe(value).replace("**", "").strip("# \n").split())
    return value if len(value) <= limit else value[:limit - 1] + "…"


def settings(config):
    return {"model": config.get("model"), "preprocessing": config.get("preprocessing"),
            **config.get("params", {})}


def score_of(result):
    score = result.get("score", result.get("validation_auc"))
    return score if type(score) in (int, float) and math.isfinite(score) else None


class Lab:
    def __init__(self):
        self.role = None
        self.busy = False
        self.action = "Waiting for the first recorded action"
        self.trial_id = None
        self.config = {}
        self.rationale = ""
        self.pending = None
        self.previous = None
        self.comparison = None
        self.changes = []
        self.discoveries = deque(maxlen=6)
        self.last_result = None
        self.selected_trial = None
        self.best_score = None
        self.reached = set()
        self.celebration_at = None

    def record(self, message, style="cyan"):
        self.discoveries.append({"message": message, "style": style})

    def update(self, event, state):
        kind = event["type"]
        if kind == "model_call_started":
            self.role, self.busy = event.get("role"), True
            self.action = "Waiting for API response · no progress estimate"
        elif kind == "model_call":
            self.role, self.busy = event.get("role"), False
            self.action = f"API call {event['status']}"
        elif kind == "tool_call":
            self.role, self.busy = event.get("role"), False
            self.action = f"Tool returned: {event.get('name', 'tool')}"
        elif kind == "decision":
            self.pending = (event["trial_id"], excerpt(event.get("message", {}).get("content")))
        elif kind == "trial_started":
            self.role, self.busy = "local", True
            self.trial_id = event["trial_id"]
            self.config = deepcopy(event.get("config", {}))
            self.rationale = self.pending[1] if self.pending and self.pending[0] == self.trial_id else ""
            self.pending = None
            self.action = f"Fitting and validating trial {self.trial_id} on this machine"
            self.comparison = self.previous["trial_id"] if self.previous else None
            self.changes = []
            if self.previous:
                before, after = settings(self.previous.get("config", {})), settings(self.config)
                def value(config, key):
                    return json.dumps(config[key], ensure_ascii=False) if key in config else "(default)"
                self.changes = [f"{key}: {value(before, key)} -> {value(after, key)}"
                                for key in sorted(before.keys() | after.keys())
                                if key not in before or key not in after or before[key] != after[key]]
        elif kind == "resources":
            if event.get("waiting") or event.get("allocated_cores"):
                self.role, self.busy = "local", True
                self.action = ("Waiting for local CPU allocation" if event.get("waiting") else
                               f"Fitting locally · {event['allocated_cores']} cores allocated")
        elif kind == "trial_finished":
            result = event["result"]
            self.role, self.busy = "local", False
            self.action = f"Trial {result['trial_id']} {result['status']}"
            self.last_result = deepcopy(result)
            if result["status"] == "completed":
                self.previous = deepcopy(result)
            else:
                self.record(self.action, "red")
        elif kind == "selection" and event.get("best"):
            best = event["best"]
            score = score_of(best)
            row = self.last_result
            if not row or row["status"] != "completed" or self.selected_trial == row["trial_id"] or score is None:
                return
            self.selected_trial = row["trial_id"]
            minimize = state.objective["direction"] == "minimize"
            improved = self.best_score is None or (score < self.best_score if minimize else score > self.best_score)
            if improved:
                self.record(f"New best · trial {best['trial_id']} · {score:.5f}", "green")
                self.celebration_at = state.elapsed
            elif score_of(row) == score:
                self.record(f"Trial {row['trial_id']} tied the best · {score:.5f}")
            else:
                self.record(f"Trial {row['trial_id']} completed · best remains trial {best['trial_id']}", "dim")
            self.best_score = score
            for target in state.targets:
                key = (target["name"], target["value"])
                if key not in self.reached and (score <= target["value"] if minimize else score >= target["value"]):
                    self.reached.add(key)
                    self.record(f"Target reached · {target['name']} ({target['value']:g})", "green")
                    self.celebration_at = state.elapsed
        elif kind in ("review", "reflection"):
            self.role, self.busy = ("supervisor" if kind == "review" else "reflection"), False
            self.action = f"{'Review' if kind == 'review' else 'Reflection'} recorded"
            if "after_trial" in event:
                self.action += f" after trial {event['after_trial']}"
        elif kind in ("failure", "run_stopped"):
            self.busy = False
            self.action = "Run stopped" if kind == "run_stopped" else "Run failure recorded"
