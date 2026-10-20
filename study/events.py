"""Harness-owned durable journal and conservative resource accounting."""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def read_events(path):
    events = []
    lines = Path(path).read_text().splitlines()
    for index, line in enumerate(lines):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            if index != len(lines) - 1:
                raise ValueError("Corrupt journal before final line")
            # A crash may leave one unfinished final append.
    return events


class Journal:
    def __init__(self, directory, started, progress=None):
        self.directory = Path(directory)
        self.started = started
        self.progress = progress

    def emit(self, event_type, **payload):
        event = {"type": event_type, "run_id": self.directory.name,
                 "timestamp": utc_now(), "elapsed_seconds": time.monotonic() - self.started, **payload}
        with (self.directory / "events.jsonl").open("a") as handle:
            handle.write(json.dumps(event, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        from .progress import format_event
        text = format_event(event, verbose=True)
        if text:
            with (self.directory / "progress.log").open("a") as handle:
                handle.write(text + "\n")
        if self.progress is not None:
            self.progress(event)
        return event


class Accounting:
    def __init__(self):
        self.known_cost = 0.0
        self.cost_complete = True
        self.token_usage_complete = True
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_tokens = 0
        self.reasoning_tokens = 0
        self.cached_tokens_complete = True
        self.reasoning_tokens_complete = True
        self.calls = 0

    def add(self, usage):
        self.calls += 1
        usage = usage if isinstance(usage, dict) else {}
        cost = usage.get("cost")
        if type(cost) in (float, int) and math.isfinite(cost) and cost >= 0:
            self.known_cost += cost
        else:
            self.cost_complete = False
        for key, attribute in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens")):
            value = usage.get(key)
            if type(value) is int and value >= 0:
                setattr(self, attribute, getattr(self, attribute) + value)
            else:
                self.token_usage_complete = False
        # These are subsets, never added to input/output totals.
        for detail, key, attribute in (
            ("prompt_tokens_details", "cached_tokens", "cached_tokens"),
            ("completion_tokens_details", "reasoning_tokens", "reasoning_tokens"),
        ):
            value = (usage.get(detail) or {}).get(key)
            if type(value) is int and value >= 0:
                setattr(self, attribute, getattr(self, attribute) + value)
            else:
                setattr(self, attribute + "_complete", False)

    def snapshot(self):
        return dict(vars(self))
