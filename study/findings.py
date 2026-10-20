"""Read-only findings derived from recorded events; no inference or agent feedback."""
import asyncio
from collections import deque
from datetime import datetime
import json
import math
from pathlib import Path
import sys
import time


def interval_seconds(value, *, allow_zero=False):
    value = float(value)
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError("Summary interval must be finite and " +
                         ("nonnegative" if allow_zero else "positive"))
    return value


class Findings:
    def __init__(self):
        from .lab import Lab
        from .live_log import LogBuffer
        from .live_lessons import LessonFeed
        self.lab = Lab()
        self.log = LogBuffer()
        self.lessons = LessonFeed()
        self.run_id = None
        self.elapsed = 0
        self.event_at = None
        self.allowance = 0
        self.config = {}
        self.resources = {}
        self.cpu = {}
        self.problem_id = ""
        self.recent = deque(maxlen=12)
        # Compact observations retain the entire search, including early gains.
        self.history = []
        self.chart_revision = 0
        self.chart_cache = {}
        self.chart_bounds = None
        self.fact = "Waiting for completed experiments."
        self.objective = {"metric": "roc_auc", "direction": "maximize"}
        self.targets = []
        self.completed = self.unsuccessful = 0
        self.first_score = None
        self.models = {}
        self.best = None
        self.accounting = {}
        self.activity = "waiting for events"
        self.review = None
        self.stopped = False

    def update(self, event):
        kind = event["type"]
        if kind == "run_started":
            self.__init__()
            problem = event.get("problem", {})
            self.objective = problem.get("evaluation", {}).get("objective", self.objective)
            self.targets = problem.get("targets", [])
            self.config = event.get("config", {})
            self.problem_id = problem.get("id", "")
            self.allowance = event.get("config", {}).get("allowance_seconds", 0)
            self.activity = "starting"
        if kind in ("trial_finished", "selection", "run_stopped"):
            self.chart_revision += 1
            self.chart_cache.clear()
        from .progress import format_event
        self.log.append(format_event(event, verbose=True))
        self.run_id = event["run_id"]
        self.elapsed = event.get("elapsed_seconds", self.elapsed)
        if event.get("timestamp"):
            self.event_at = datetime.fromisoformat(event["timestamp"])
        if "accounting" in event:
            self.accounting = event["accounting"]
        self.lab.update(event, self)
        if kind == "lesson_memory":
            self.lessons.update(event.get("lessons", []), source=event.get("role") or self.lab.role)
        if kind == "model_call_started":
            self.activity = f"{event.get('role', 'agent')} model call in progress"
        elif kind == "model_call":
            self.activity = f"{event.get('role', 'agent')} model call {event['status']}"
        elif kind == "trial_started":
            self.activity = f"local trial {event['trial_id']} in progress"
            if self.config.get("max_cores") is None:
                self.resources = {"max_cores": 1, "active_cores": 1}
        elif kind == "trial_finished":
            if self.config.get("max_cores") is None:
                self.resources = {"max_cores": 1, "active_cores": 0}
            result = event["result"]
            self.activity = f"trial {result['trial_id']} {result['status']}"
            score = result.get("score", result.get("validation_auc"))
            if type(score) not in (int, float) or not math.isfinite(score):
                score = None
            row = {"trial_id": result["trial_id"], "score": score,
                   "config": result.get("config", {}), "status": result["status"],
                   "outcome": "Unselected" if result["status"] == "completed" else result["status"],
                   "elapsed": self.elapsed}
            self.recent.append(row)
            if result["status"] != "completed":
                row["score"] = None
                self.unsuccessful += 1
                return
            self.completed += 1
            if score is None:
                return
            account = self.accounting
            self.history.append({"trial_id": result["trial_id"], "score": score, "best": None,
                "elapsed": self.elapsed,
                "cost": account.get("known_cost") if account.get("cost_complete") else None,
                "tokens": account["input_tokens"] + account["output_tokens"]
                    if account.get("token_usage_complete") and
                    "input_tokens" in account and "output_tokens" in account else None})
            for previous in reversed(list(self.recent)[:-1]):
                before, after = previous["config"], row["config"]
                if (previous["score"] == score and before.get("model") == after.get("model")
                        and before.get("params") == after.get("params")
                        and before.get("preprocessing") != after.get("preprocessing")):
                    self.fact = f"Changing scaling to {after.get('preprocessing')} matched trial {previous['trial_id']}'s score with the same model parameters."
                    break
            else:
                self.fact = f"Trial {result['trial_id']} completed with validation score {score:.6f}."
            if self.first_score is None:
                self.first_score = score
            model = result.get("config", {}).get("model", "unspecified")
            previous = self.models.get(model)
            minimize = self.objective["direction"] == "minimize"
            if previous is None or (score < previous if minimize else score > previous):
                self.models[model] = score
        elif kind == "selection":
            self.best = event.get("best")
            if self.best and self.recent:
                best_score = self.best.get("score", self.best.get("validation_auc"))
                row = self.recent[-1]
                if row["status"] == "completed" and row["score"] is not None:
                    row["outcome"] = ("New best" if row["trial_id"] == self.best["trial_id"] else
                                      "Tied best" if row["score"] == best_score else "Not best")
                    if self.history and self.history[-1]["trial_id"] == row["trial_id"]:
                        self.history[-1]["best"] = best_score
        elif kind == "review":
            self.review = (event["after_trial"], event["feedback"])
        elif kind == "run_stopped":
            summary = event["summary"]
            self.best = summary.get("best")
            self.accounting = summary.get("accounting", self.accounting)
            self.activity = f"stopped: {summary['stop_reason']}"
            self.stopped = True
            if self.config.get("max_cores") is None:
                self.resources = {"max_cores": 1, "active_cores": 0}
        elif kind == "resources":
            self.resources = {key: event[key] for key in ("max_cores", "active_cores", "allocated_cores", "waiting")}
            if event["waiting"]:
                self.activity = "waiting for local CPU allocation"
            elif event["allocated_cores"]:
                self.activity = f"local training on {event['allocated_cores']} cores"
        elif kind == "failure":
            self.activity = f"failure: {event['error']}"

    def render(self):
        from .progress import _safe, _usage
        if self.run_id is None:
            return ""
        lines = [f"[{self.run_id}] FINDINGS — last event +{self.elapsed:.1f}s",
                 f"  {self.completed} completed, {self.unsuccessful} unsuccessful; {self.activity}."]
        metric = self.objective["metric"]
        minimize = self.objective["direction"] == "minimize"
        score = self.best.get("score", self.best.get("validation_auc")) if self.best else None
        if score is not None:
            lines.append(f"  Best validation {metric}: {score:.6f} (trial {self.best['trial_id']}).")
            if self.first_score is not None:
                improvement = (self.first_score - score) if minimize else (score - self.first_score)
                lines.append(f"  Absolute improvement over first completed trial: {improvement:+.6f}.")
            if self.targets:
                lines.append("  " + "; ".join(
                    f"{t['name']} " + ("reached" if (score <= t["value"] if minimize else
                    score >= t["value"]) else "not reached") + f" ({t['value']:g})" for t in self.targets) + ".")
        else:
            lines.append("  No selected model yet.")
        if self.models:
            lines.append("  Best observed by model: " + "; ".join(
                f"{name} {value:.6f}" for name, value in self.models.items()) + ".")
        if self.accounting:
            lines.append("  " + _usage(self.accounting))
        if self.review:
            after, feedback = self.review
            from .lab import sentence_summary
            summary = sentence_summary(feedback, limit=280) or "The full review is saved in the trace."
            lines.append(f"  Supervisor after trial {after} (model interpretation): {summary}")
        return _safe("\n".join(lines))


class EventTail:
    """Read only complete appended lines, including split UTF-8 writes."""
    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        self.handle = self.path.open("rb")
        return self

    def __exit__(self, *exc):
        self.handle.close()

    def read(self):
        events = []
        while True:
            offset = self.handle.tell()
            line = self.handle.readline()
            if not line.endswith(b"\n"):
                self.handle.seek(offset)
                return events
            try:
                events.append(json.loads(line))
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise ValueError(f"Corrupt complete event at byte {offset}") from error


async def watch(output, *, interval=15, once=False, stream=None, animate=True):
    """Attach to a single run without modifying it or loading credentials."""
    interval = interval_seconds(interval)
    stream = sys.stdout if stream is None else stream
    state = Findings()
    from .terminal import StatusLine
    display = StatusLine(stream, animate=animate and not once)
    previous = ""
    next_update = 0
    next_poll = 0
    output = Path(output)
    try:
        with EventTail(output / "events.jsonl") as tail:
            while True:
                now = time.monotonic()
                if now >= next_poll:
                    for event in tail.read():
                        state.update(event)
                    # Recovery freezes summary.json without appending a stop event.
                    if not state.stopped and (output / "summary.json").exists():
                        summary = json.loads((output / "summary.json").read_text())
                        state.update({"type": "run_stopped", "run_id": state.run_id or output.name,
                                      "summary": summary})
                    next_poll = now + min(1, interval)
                if now >= next_update or state.stopped or once:
                    text = state.render()
                    if text and text != previous and (not display.enabled or state.stopped or once):
                        display.write(text)
                        previous = text
                    next_update = now + interval
                if state.stopped or once:
                    return
                display.draw(state, detailed=True)
                await asyncio.sleep(min(.25 if display.enabled else 1, interval))
    finally:
        display.clear()
