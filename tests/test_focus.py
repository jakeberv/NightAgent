import io
import os

import pytest
from rich.cells import cell_len
from rich.console import Console

from study.findings import Findings
from study.terminal import dashboard


def state_for_focus():
    state = Findings()
    def emit(kind, **data):
        state.update(dict(type=kind, run_id="magic-demo", elapsed_seconds=120, **data))
    emit("run_started", config={"allowance_seconds": 300, "trial_cap": 12, "dollar_cap": 3,
                               "condition": "periodic_reflection"}, problem={"id": "MAGIC",
        "targets": [{"name": "milestone", "value": .93}, {"name": "stretch", "value": .95}]})
    emit("trial_finished", result={"trial_id": 1, "score": .91, "status": "completed",
                                   "config": {"model": "random_forest", "params": {"n_estimators": 100}}})
    emit("selection", best={"trial_id": 1, "score": .91})
    emit("decision", trial_id=2, message={"content": "## Rationale\nMore trees may improve validation performance. This tests model capacity."})
    emit("trial_started", trial_id=2, config={"model": "random_forest", "params": {"n_estimators": 200}})
    state.accounting = {"known_cost": .24, "cost_complete": False}
    state.cpu = {"percent": 25}
    state.resources = {"max_cores": 4, "active_cores": 2}
    return state


@pytest.mark.parametrize("width,height", [(120,38), (80,24), (55,30), (40,16)])
def test_focus_view_prioritizes_activity_results_and_constraints_without_dense_tables(width, height):
    state = state_for_focus()
    output = io.StringIO()
    Console(file=output, width=width, height=height, color_system=None).print(
        dashboard(state, width=width, height=height, focus=True))
    rendered = output.getvalue()
    assert "0.91000" in rendered and "$0.2400 known" in rendered and "3:00" in rendered
    assert "trial 2" in rendered.lower()
    assert "Recent experiments" not in rendered and "CPU hist" not in rendered and "Trial scores" not in rendered
    assert "excerpt" not in rendered.lower() and "…" not in rendered
    assert len(rendered.splitlines()) <= height
    assert all(cell_len(line) <= width for line in rendered.splitlines())


def test_focus_retains_failure_and_unknown_accounting_and_supports_minimization():
    state = state_for_focus()
    state.objective = {"metric": "rmse", "direction": "minimize"}
    state.first_score = 1.0
    state.best = {"score": .8, "trial_id": 1}
    state.update({"type": "trial_finished", "run_id": "magic-demo", "result": {
        "trial_id": 2, "status": "timeout"}})
    output = io.StringIO()
    Console(file=output, width=80, height=24, color_system=None).print(dashboard(state, width=80, height=24, focus=True))
    rendered = output.getvalue()
    assert "timeout" in rendered and "1 unsuccessful" in rendered
    assert "+0.20000" in rendered and "rmse" in rendered and "known" in rendered


def test_visual_agent_summaries_are_whole_sentences_and_untrusted_text_is_literal():
    from study.lab import sentence_summary
    assert sentence_summary("## Rationale\nMore trees may help. Another reason follows.", limit=25) == "More trees may help."
    assert sentence_summary("## Rationale\n" + "A long sentence " * 60 + ".", limit=80) == ""
    assert sentence_summary("**Rationale:**\n- Controlled single-parameter change", limit=80) == ""
    assert sentence_summary("The value is 0.9319. This matters.", limit=24) == "The value is 0.9319."
    state = state_for_focus()
    state.review = (1, "The [red]model[/red] improved.\x1b[2J Next sentence.")
    for focus in [False, True]:
        output = io.StringIO()
        Console(file=output, width=120, height=40, color_system=None).print(
            dashboard(state, width=120, height=40, focus=focus))
        assert "excerpt" not in output.getvalue().lower()
        assert "\x1b" not in output.getvalue()


@pytest.fixture
def keyboard_pty():
    pty = pytest.importorskip("pty")
    master, slave = pty.openpty()
    stream = os.fdopen(os.dup(slave), "r")
    try:
        yield master, slave, stream
    finally:
        stream.close()
        os.close(slave)
        os.close(master)


def test_keyboard_reads_toggle_without_enter_and_restores_terminal(keyboard_pty):
    import termios
    from study.keyboard import ViewKeys
    master, slave, stream = keyboard_pty
    before = termios.tcgetattr(slave)
    keys = ViewKeys(stream)
    try:
        assert keys.start()
        active = termios.tcgetattr(slave)
        assert not active[3] & termios.ECHO and not active[3] & termios.ICANON
        assert active[3] & termios.ISIG  # Ctrl+C remains a signal.
        assert keys.poll() == 0
        os.write(master, b"f")
        assert keys.poll() == 1
        os.write(master, b"Ff")
        assert keys.poll() == 2
        os.write(master, b"\x1b[1;5F")  # Modified End key is not the F shortcut.
        assert keys.poll() == 0
    finally:
        keys.close()
    after = termios.tcgetattr(slave)
    # BSD marks pending canonical input for reprocessing on the mode change.
    # PENDIN is kernel state, not a terminal setting that the application owns.
    after[3] &= ~getattr(termios, "PENDIN", 0)
    before[3] &= ~getattr(termios, "PENDIN", 0)
    assert after == before


def test_keyboard_does_not_read_redirected_input():
    from study.keyboard import ViewKeys
    stream = io.StringIO("f")
    keys = ViewKeys(stream)
    assert not keys.start()
    assert keys.poll() == 0
    assert stream.tell() == 0


def test_focus_keyboard_toggle_reuses_live_screen_and_restores_tty_on_clear(monkeypatch, keyboard_pty):
    import termios
    from study.terminal import StatusLine
    master, slave, input_stream = keyboard_pty
    before = termios.tcgetattr(slave)
    class Terminal(io.StringIO):
        def isatty(self):
            return True
    monkeypatch.setenv("TERM", "xterm")
    stream = Terminal()
    display = StatusLine(stream, input_stream=input_stream)
    display.console.size = (100, 36)
    state = state_for_focus()
    try:
        display.draw(state, detailed=True)
        original_live = display.live
        os.write(master, b"f")
        offset = len(stream.getvalue())
        display.draw(state, detailed=True)
        assert display.focus and display.live is original_live
        frame = stream.getvalue()[offset:]
        assert "FOCUS" in frame and "Recent experiments" not in frame
        assert "\x1b[2J" not in frame and "\x1b[2K" not in frame
        os.write(master, b"f")
        display.draw(state, detailed=True)
        assert not display.focus and display.live is original_live
    finally:
        display.clear()
    after = termios.tcgetattr(slave)
    # BSD marks pending canonical input for reprocessing on the mode change.
    # PENDIN is kernel state, not a terminal setting that the application owns.
    after[3] &= ~getattr(termios, "PENDIN", 0)
    before[3] &= ~getattr(termios, "PENDIN", 0)
    assert after == before
    assert stream.getvalue().count("\x1b[?1049h") == 1


def test_progress_restores_input_even_if_refresh_task_fails(monkeypatch, keyboard_pty):
    import asyncio
    import termios
    from study.progress import ConsoleProgress
    from study.terminal import StatusLine
    master, slave, input_stream = keyboard_pty
    monkeypatch.setenv("TERM", "xterm")
    class Terminal(io.StringIO):
        def isatty(self):
            return True
    async def scenario():
        progress = ConsoleProgress(stream=Terminal())
        progress.display = StatusLine(progress.stream, input_stream=input_stream)
        async def failed_refresh():
            progress.display.draw(state_for_focus(), detailed=True)
            raise ValueError("render error")
        progress.task = asyncio.create_task(failed_refresh())
        await asyncio.sleep(0)
        with pytest.raises(ValueError, match="render error"):
            await progress.__aexit__(None, None, None)
        assert progress.display.live is None
        assert termios.tcgetattr(slave)[3] & termios.ECHO
    asyncio.run(scenario())


def test_keyboard_ignores_split_escape_sequences_and_bracketed_paste(keyboard_pty):
    from study.keyboard import ViewKeys
    master, _, stream = keyboard_pty
    keys = ViewKeys(stream)
    try:
        keys.start()
        os.write(master, b"\x1b[1;")
        assert keys.poll() == 0
        os.write(master, b"5F\x1b[200~fff")
        assert keys.poll() == 0
        os.write(master, b"f\x1b[201~f")
        assert keys.poll() == 1
    finally:
        keys.close()


def test_real_terminal_toggle_and_ctrl_c_restore_screen_and_input(keyboard_pty):
    import select
    import subprocess
    import sys
    import termios
    import time
    master, slave, _ = keyboard_pty
    script = '''
import asyncio, fcntl, sys, termios
from study.progress import ConsoleProgress
fcntl.ioctl(sys.stdin.fileno(), termios.TIOCSCTTY, 0)
async def main():
    async with ConsoleProgress(summary_interval=0) as progress:
        progress({'type':'run_started','run_id':'keyboard-demo','config':{'allowance_seconds':300,'trial_cap':12,'dollar_cap':3}})
        progress({'type':'model_call_started','run_id':'keyboard-demo','role':'researcher'})
        await asyncio.Event().wait()
try:
    asyncio.run(main())
except KeyboardInterrupt:
    attrs = termios.tcgetattr(sys.stdin.fileno())
    print(f'RESTORED_AFTER_CTRL_C echo={bool(attrs[3] & termios.ECHO)} canon={bool(attrs[3] & termios.ICANON)}', flush=True)
'''
    process = subprocess.Popen([sys.executable, "-c", script], stdin=slave, stdout=slave, stderr=slave,
                               start_new_session=True, env={**os.environ, "TERM": "xterm", "COLUMNS": "80", "LINES": "24"})
    output = b""
    def until(marker):
        nonlocal output
        deadline = time.monotonic() + 10
        while marker not in output and time.monotonic() < deadline:
            if select.select([master], [], [], .1)[0]:
                output += os.read(master, 65536)
        assert marker in output, output.decode(errors="replace")[-2000:]
    try:
        until(b"Live log")
        os.write(master, b"f")
        until(b"FOCUS")
        os.write(master, b"\x03")
        until(b"RESTORED_AFTER_CTRL_C")
        assert process.wait(timeout=5) == 0
        assert b"echo=True canon=True" in output
        assert output.index(b"\x1b[?1049l") < output.index(b"RESTORED_AFTER_CTRL_C")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


@pytest.mark.parametrize("animate,detailed", [(False, True), (True, False)])
def test_plain_and_verbose_modes_leave_keyboard_untouched(monkeypatch, keyboard_pty, animate, detailed):
    import termios
    from study.terminal import StatusLine
    _, slave, input_stream = keyboard_pty
    class Terminal(io.StringIO):
        def isatty(self):
            return True
    monkeypatch.setenv("TERM", "xterm")
    before = termios.tcgetattr(slave)
    display = StatusLine(Terminal(), input_stream=input_stream, animate=animate)
    try:
        display.draw(state_for_focus(), detailed=detailed)
        assert termios.tcgetattr(slave) == before
        assert not display.keys.active
    finally:
        display.clear()


def test_nonterminal_fd_errors_do_not_break_display(tmp_path):
    from study.keyboard import ViewKeys
    class LooksInteractive:
        def __init__(self, stream):
            self.stream = stream
        def isatty(self):
            return True
        def fileno(self):
            return self.stream.fileno()
    with (tmp_path / "input").open("w+") as stream:
        keys = ViewKeys(LooksInteractive(stream))
        assert not keys.start()
        assert not keys.active
        keys.close()


@pytest.mark.parametrize("sentence", [
    "Increasing regularization, e.g. from 0.1 to 0.2, may improve generalization.",
    "Use the prior settings (e.g. 200 trees) to establish the comparison.",
    "The reviewer, Dr. Smith, suggests testing a stronger regularizer.",
])
def test_sentence_summaries_do_not_stop_at_abbreviations(sentence):
    from study.lab import sentence_summary
    from study.focus import fitting_summary
    assert sentence_summary(sentence, limit=40) == ""
    assert fitting_summary(sentence, 40, 1, "") == ""
    assert sentence_summary(sentence, limit=200) == sentence


def test_narrow_discovery_fallback_does_not_claim_completed_run_is_still_waiting():
    state = state_for_focus()
    state.lab.record("The external validation milestone for the production model (0.93) has been reached.", "green")
    output = io.StringIO()
    Console(file=output, width=40, height=24, color_system=None).print(dashboard(state, width=40, height=24, focus=True))
    rendered = output.getvalue()
    assert "A new result has been recorded." in rendered
    assert "waiting for a completed" not in rendered.lower()


def test_log_keyboard_toggle_preserves_stream_and_ignores_pasted_shortcuts(monkeypatch, keyboard_pty):
    from study.terminal import StatusLine
    from test_terminal import Terminal
    master, _, input_stream = keyboard_pty
    monkeypatch.setenv('TERM', 'xterm')
    stream = Terminal()
    display = StatusLine(stream, input_stream=input_stream)
    display.console.size = (140, 36)
    state = state_for_focus()
    state.update({'type': 'failure', 'run_id': 'magic-demo', 'error': 'VISIBLE_LOG_LINE'})
    try:
        display.draw(state, detailed=True)
        original_live = display.live
        assert 'VISIBLE_LOG_LINE' in stream.getvalue()
        os.write(master, b'l')
        offset = len(stream.getvalue())
        display.draw(state, detailed=True)
        assert not display.show_log and 'Live log' not in stream.getvalue()[offset:]
        os.write(master, b'\x1b[200~lL\x1b[201~')
        display.draw(state, detailed=True)
        assert not display.show_log
        os.write(master, b'f')
        display.draw(state, detailed=True)
        assert display.focus
        os.write(master, b'L')
        offset = len(stream.getvalue())
        display.draw(state, detailed=True)
        assert display.show_log and not display.focus
        assert 'VISIBLE_LOG_LINE' in stream.getvalue()[offset:]
        assert display.live is original_live
        assert '\x1b[2J' not in stream.getvalue()[offset:]
        assert '\x1b[2K' not in stream.getvalue()[offset:]
    finally:
        display.clear()
    assert stream.getvalue().count('\x1b[?1049h') == 1
