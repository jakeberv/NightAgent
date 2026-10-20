"""Optional, nonblocking view keys for an interactive POSIX terminal."""
from copy import deepcopy
import os
import select
import sys

try:
    import termios
except ImportError:
    termios = None

TERMINAL_ERRORS = (OSError, ValueError, AttributeError) + ((termios.error,) if termios else ())


class ViewKeys:
    def __init__(self, stream=None):
        self.stream = sys.stdin if stream is None else stream
        self.fd = None
        self.saved = None
        self.attempted = False
        self.escape = b""
        self.pasting = False
        self.log_toggles = 0

    @property
    def active(self):
        return self.saved is not None

    def start(self):
        if self.attempted:
            return self.active
        self.attempted = True
        if termios is None:
            return False
        try:
            if not self.stream.isatty():
                return False
            self.fd = self.stream.fileno()
            original = termios.tcgetattr(self.fd)
            changed = deepcopy(original)
            # Keep ISIG so Ctrl+C still interrupts the runner normally.
            changed[3] &= ~(termios.ECHO | termios.ICANON)
            changed[6][termios.VMIN] = 0
            changed[6][termios.VTIME] = 0
            self.saved = original
            termios.tcsetattr(self.fd, termios.TCSANOW, changed)
            return True
        except TERMINAL_ERRORS:
            self.close()
            self.attempted = True
            return False

    def poll(self):
        self.log_toggles = 0
        if not self.active:
            return 0
        try:
            if not select.select([self.fd], [], [], 0)[0]:
                return 0
            data = os.read(self.fd, 256)
            if not data:
                self.close()
                return 0
        except (OSError, ValueError):
            self.close()
            return 0
        toggles = 0
        for byte in data:
            if self.escape:
                self.escape += bytes([byte])
                if self.escape in (b"\x1b[", b"\x1bO"):
                    continue
                if len(self.escape) == 2 or 0x40 <= byte <= 0x7e or len(self.escape) > 32:
                    if self.escape == b"\x1b[200~":
                        self.pasting = True
                    elif self.escape == b"\x1b[201~":
                        self.pasting = False
                    self.escape = b""
            elif byte == 27:
                self.escape = b"\x1b"
            elif not self.pasting and byte in (ord("f"), ord("F")):
                toggles += 1
            elif not self.pasting and byte in (ord("l"), ord("L")):
                self.log_toggles += 1
        return toggles

    def close(self):
        saved, self.saved = self.saved, None
        try:
            if saved is not None:
                termios.tcsetattr(self.fd, termios.TCSANOW, saved)
        except TERMINAL_ERRORS:
            pass  # A disconnected terminal must not invalidate saved results.
        finally:
            self.fd = None
            self.attempted = False
            self.escape = b""
            self.pasting = False
