"""Transient terminal panel or status line; no animation in logs or pipes."""
from datetime import datetime, timezone
import os
import shutil
import textwrap


def _duration(seconds):
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}:{seconds:02d}"


class StatusLine:
    def __init__(self, stream, *, animate=True):
        self.stream = stream
        self.enabled = bool(animate and getattr(stream, "isatty", lambda: False)()
                            and os.environ.get("TERM") != "dumb")
        self.visible_rows = 0
        self.frame = 0
        encoding = getattr(stream, "encoding", None) or "utf-8"
        self.frames = "|/-\\" if encoding.lower() in ("ascii", "us-ascii") else "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def clear(self):
        if self.visible_rows:
            self.stream.write("\r\x1b[2K")
            for _ in range(self.visible_rows - 1):
                self.stream.write("\x1b[1A\r\x1b[2K")
            self.stream.flush()
            self.visible_rows = 0

    def write(self, text):
        self.clear()
        print(text, file=self.stream, flush=True)

    def draw(self, state, *, detailed=False):
        if not self.enabled or not state.run_id or state.stopped:
            self.clear()
            return
        elapsed = state.elapsed
        if state.event_at is not None:
            elapsed += max(0, (datetime.now(timezone.utc) - state.event_at).total_seconds())
        activity = state.activity.replace(" model call in progress", " API").replace("local ", "")
        activity = activity.replace(" in progress", " fitting")
        size = shutil.get_terminal_size(fallback=(100, 24))
        width = max(2, size.columns)
        timing = _duration(elapsed)
        if state.allowance:
            timing += "/" + _duration(state.allowance)
            if width >= 100:
                filled = min(8, int(8 * elapsed / state.allowance))
                timing += " [" + "=" * filled + "-" * (8 - filled) + "]"
        trials = f"{state.completed} ok"
        if state.unsuccessful:
            trials += f"/{state.unsuccessful} failed"
        best = state.best or {}
        score = best.get("score", best.get("validation_auc"))
        best_text = f"best {score:.5f}" if score is not None else "best —"
        account = state.accounting
        cost = (f"${account['known_cost']:.4f}" +
                ("" if account.get("cost_complete") else " known")) if account else "$pending"
        text = f"{self.frames[self.frame % len(self.frames)]} {activity[:24]} | {timing} | {trials} | {best_text} | {cost}"
        self.frame += 1
        from .progress import _safe
        lines = [_safe(text).replace("\n", " ")[:width - 1]]
        if detailed:
            lines = [f"NIGHTAGENT | LIVE FINDINGS | {state.run_id}"[:width - 1], lines[0]]
            for line in state.render().splitlines()[1:]:
                # Keep observations legible at narrow widths without dumping full feedback.
                wrapped = textwrap.wrap(line, width=width - 1, subsequent_indent="  ")
                lines.extend(wrapped[:3])
                if len(wrapped) > 3:
                    lines[-1] = lines[-1][:max(0, width - 2)] + "…"
            lines = lines[:max(1, size.lines - 2)]
        self.clear()
        self.stream.write("\r\x1b[2K" + "\n".join(_safe(line) for line in lines))
        self.stream.flush()
        self.visible_rows = len(lines)
