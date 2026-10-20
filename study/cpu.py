"""Nonblocking, display-only host CPU measurements; never changes scheduling."""
from collections import deque
import math
import time

try:
    import psutil
except ImportError:  # Older environments can still run; show unavailable honestly.
    psutil = None


class HostCPU:
    def __init__(self):
        self.last = None
        self.primed = False
        self.percent = None
        self.status = "sampling"
        self.history = deque(maxlen=30)

    def sample(self):
        now = time.monotonic()
        if self.last is None or now - self.last >= 1:
            self.last = now
            try:
                if psutil is None:
                    raise RuntimeError("psutil is not installed")
                value = psutil.cpu_percent(interval=None)
                if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
                    raise ValueError("Invalid host CPU measurement")
                if self.primed:
                    self.percent = value
                    self.status = "measured"
                    self.history.append(value)
                else:
                    # The first nonblocking reading has no observation interval.
                    self.primed = True
                    self.percent = None
                    self.status = "sampling"
            except (OSError, RuntimeError, ValueError):
                self.percent = None
                self.primed = False
                self.status = "unavailable"
                self.history.append(None)
        return {"percent": self.percent, "status": self.status, "history": list(self.history)}
