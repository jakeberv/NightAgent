"""Bounded, read-only presentation state from the runner's existing events."""
from collections import deque
from copy import deepcopy
import json
import math
import re


def complete_sentences(prose):
    """Split terminal prose without treating common abbreviations as endings."""
    start = 0
    for match in re.finditer(r"[.!?](?:[\"'’)\]]*)(?=\s|$)", prose):
        prefix = prose[:match.start() + 1]
        if prose[match.start()] == "." and (
            re.search(r"\b(?:e\.g|i\.e|etc|vs|approx|fig|eq|dr|mr|mrs|ms|prof|sr|jr)\.$", prefix, re.I)
            or re.search(r"\b[A-Z]\.$", prefix)
        ):
            continue
        sentence = prose[start:match.end()].strip()
        if sentence:
            yield sentence
        start = match.end()


def sentence_summary(value, limit=240):
    """Select whole prose sentences; never manufacture a clipped quotation.

    Lists/code/headings are not prose. If no sentence fits, the view uses a
    factual summary of the recorded experiment instead of truncating the agent.
    """
    from .progress import _safe
    if not isinstance(value, str):
        return ""
    value = _safe(value)
    value = re.sub(r"```.*?```", "", value, flags=re.S)
    sections = re.split(r"(?im)^[ \t]*(?:#{1,6}[ \t]+|\*\*)(?:rationale|strategy)[ \t]*:?(?:\*\*)?[ \t]*\n", value)
    preferred = sections[1:] + sections[:1] if len(sections) > 1 else sections
    for section in preferred:
        lines = [line.strip().replace("**", "") for line in section.splitlines()
                 if line.strip() and not re.match(r"^\s*(?:#|[-*] |\d+[.)] )", line)]
        prose = " ".join(lines)
        sentences = complete_sentences(prose)
        chosen = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > limit:
                continue
            if len(" ".join(chosen + [sentence])) > limit:
                break
            chosen.append(sentence)
            if len(chosen) == 2:
                break
        if chosen:
            return " ".join(chosen)
    return ""


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
        self.phase_started = None
        self.guidance = None
        self.action = "Waiting for the first recorded action"
        self.trial_id = None
        self.config = {}
        self.rationale = ""
        self.pending = None
        self.previous = None
        self.completed_configs = deque(maxlen=80)
        self.intent = None
        self.comparison = None
        self.comparison_available = False
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
            self.phase_started = state.elapsed
            self.action = "Waiting for API response · no progress estimate"
        elif kind == "model_call":
            self.role, self.busy = event.get("role"), False
            self.action = f"API call {event['status']}"
        elif kind == "tool_call":
            self.role, self.busy = event.get("role"), False
            self.action = f"Tool returned: {event.get('name', 'tool')}"
        elif kind == "decision":
            content = event.get("message", {}).get("content")
            # Legacy traces used prose decisions; contract payloads are not prose.
            rationale = (sentence_summary(content) if isinstance(content, str)
                         and not content.lstrip().startswith(("{", "[")) else "")
            self.pending = (event["trial_id"], rationale)
        elif kind == "trial_started":
            self.role, self.busy = "local", True
            self.phase_started = state.elapsed
            self.trial_id = event["trial_id"]
            self.config = deepcopy(event.get("config", {}))
            self.intent = deepcopy(event.get("intent"))
            if isinstance(self.intent, dict):
                self.rationale = sentence_summary(self.intent.get("summary"))
                self.comparison = self.intent.get("baseline_trial_id")
                baseline = next((row for row in reversed(self.completed_configs)
                                 if row["trial_id"] == self.comparison), None)
            else:
                self.rationale = self.pending[1] if self.pending and self.pending[0] == self.trial_id else ""
                baseline = self.previous
                self.comparison = baseline["trial_id"] if baseline else None
            self.pending = None
            self.action = f"Fitting and validating trial {self.trial_id} on this machine"
            self.comparison_available = baseline is not None
            self.changes = []
            if baseline:
                before, after = settings(baseline.get("config", {})), settings(self.config)
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
                self.completed_configs.append({"trial_id": result["trial_id"],
                                               "config": deepcopy(result.get("config", {}))})
            else:
                self.record(f"Trial {result['trial_id']} ended with status {result['status']}.", "red")
        elif kind == "experiment_diagnostic":
            warning = sentence_summary(event.get("warning"), limit=480)
            if warning:
                self.record(warning, "yellow")
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
                self.record(f"Trial {best['trial_id']} set a new best score of {score:.5f}.", "green")
                self.celebration_at = state.elapsed
            elif score_of(row) == score:
                self.record(f"Trial {row['trial_id']} tied the best score at {score:.5f}.")
            else:
                self.record(f"Trial {row['trial_id']} completed; trial {best['trial_id']} remains the best.", "dim")
            self.best_score = score
            for target in state.targets:
                key = (target["name"], target["value"])
                if key not in self.reached and (score <= target["value"] if minimize else score >= target["value"]):
                    self.reached.add(key)
                    self.record(f"The {target['name']} target ({target['value']:g}) has been reached.", "green")
                    self.celebration_at = state.elapsed
        elif kind in ("review", "reflection"):
            self.role, self.busy = ("supervisor" if kind == "review" else "reflection"), False
            self.action = f"{'Review' if kind == 'review' else 'Reflection'} recorded"
            if "after_trial" in event:
                self.action += f" after trial {event['after_trial']}"
            # Only accepted review/reflection events enter the narrative, never
            # attempted contracts (which may have failed validation).
            self.guidance = {"role": self.role, "after_trial": event.get("after_trial"),
                             "contract": deepcopy(event.get("contract") or {}),
                             "summary": event.get("feedback" if kind == "review" else "reflection", "")}
        elif kind in ("failure", "run_stopped"):
            self.busy = False
            self.action = "Run stopped" if kind == "run_stopped" else "Run failure recorded"
