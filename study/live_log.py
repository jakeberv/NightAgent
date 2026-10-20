"""Bounded display tail of the full readable event log; never agent context."""
from collections import deque

from rich.panel import Panel
from rich.text import Text


class LogBuffer:
    def __init__(self, max_lines=2000, max_chars=262144):
        self.lines = deque()
        self.max_lines = max_lines
        self.max_chars = max_chars
        self.characters = 0
        self.version = 0
        self.cache = None

    def append(self, value):
        if not value:
            return
        from .progress import _safe
        value = _safe(value)[-self.max_chars:]
        for line in value.splitlines():
            self.lines.append(line)
            self.characters += len(line) + 1
            while self.lines and (len(self.lines) > self.max_lines or self.characters > self.max_chars):
                if len(self.lines) == 1:
                    removed = self.lines.pop()
                    tail = removed[-max(0, self.max_chars - 1):]
                    self.lines.append(tail)
                    self.characters = len(tail) + 1
                    break
                self.characters -= len(self.lines.popleft()) + 1
        self.version += 1
        self.cache = None

    def tail(self, console, width, rows):
        key = (self.version, width, rows)
        if self.cache and self.cache[0] == key:
            return self.cache[1]
        lines = []
        for source in reversed(self.lines):
            wrapped = Text(source).wrap(console, max(1, width), overflow='fold', no_wrap=False)
            lines[:0] = [line.plain for line in wrapped][-max(0, rows - len(lines)):]
            if len(lines) >= rows:
                break
        result = Text('\n'.join(lines), overflow='fold')
        self.cache = (key, result)
        return result


class LogTail:
    def __init__(self, buffer, rows):
        self.buffer = buffer
        self.rows = rows

    def __rich_console__(self, console, options):
        if not self.buffer.lines:
            yield Text('Waiting for log events.', style='dim')
        else:
            yield self.buffer.tail(console, options.max_width, self.rows)


def log_panel(state, height, *, shortcut=False):
    return Panel(LogTail(state.log, max(1, height - 2)), title=Text('Live log · following'),
                 subtitle=Text('l Hide · progress.log' if shortcut else 'Full history: progress.log'),
                 height=height, padding=(0, 1), border_style='bright_black')
