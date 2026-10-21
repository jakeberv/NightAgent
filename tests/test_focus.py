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


def render_focus(state, width=80, height=24):
    output = io.StringIO()
    Console(file=output, width=width, height=height, color_system=None).print(
        dashboard(state, width=width, height=height, focus=True, shortcut=True))
    return output.getvalue()


def structured_focus():
    state = state_for_focus()
    state.update({"type": "trial_started", "run_id": "magic-demo", "elapsed_seconds": 120,
                  "trial_id": 2, "config": {"model": "random_forest", "params": {"n_estimators": 200}},
                  "intent": {"summary": "Test a larger forest.", "baseline_trial_id": 1,
                             "hypothesis": "More trees may reduce prediction variance.",
                             "change": "Increase the forest from 100 to 200 trees.",
                             "expected_outcome": "Validation AUC may improve over trial 1."}})
    return state


def test_focus_explains_hypothesis_change_and_expected_outcome_without_extra_calls():
    state = structured_focus()
    rendered = render_focus(state)
    assert "More trees may reduce prediction variance." in rendered
    assert "Increase the forest from 100 to 200 trees." in rendered
    assert "Validation AUC may improve over trial 1." in rendered
    assert "Agent hypothesis:" in rendered and "Prediction (unverified):" in rendered
    assert "0.91000" in rendered and "$0.2400 known" in rendered
    assert "l Log" in rendered


@pytest.mark.parametrize("role,purpose", [
    ("researcher", "choosing the next experiment"),
    ("supervisor", "reviewing the validation evidence"),
    ("reflection", "reassessing the search strategy"),
])
def test_focus_explains_pending_role_and_times_call_not_last_event(monkeypatch, role, purpose):
    state = structured_focus()
    state.update({"type": "model_call_started", "run_id": "magic-demo", "role": role,
                  "elapsed_seconds": 130})
    # An unrelated recorded event must not reset the call timer.
    state.update({"type": "experiment_diagnostic", "run_id": "magic-demo", "elapsed_seconds": 139,
                  "warning": "The same settings were previously evaluated."})
    monkeypatch.setattr("study.terminal.elapsed_now", lambda state: 145)
    rendered = render_focus(state, height=30)
    assert purpose in rendered
    assert "API response pending · 0:15 elapsed" in rendered
    assert "Last experiment" in rendered  # Old intent is not the new agent's live thinking.


@pytest.mark.parametrize("kind,role,fields,expected", [
    ("review", "supervisor", {"assessment": "The improvement is still uncertain.",
                              "recommendation": "Compare a shallower forest next."},
     "Compare a shallower forest next."),
    ("reflection", "reflection", {"what_changed": "Larger forests have stopped improving.",
                                  "next_comparison": "Compare gradient boosting with the forest."},
     "Compare gradient boosting with the forest."),
])
def test_focus_keeps_recorded_guidance_during_next_researcher_call(kind, role, fields, expected):
    state = structured_focus()
    state.update({"type": kind, "run_id": "magic-demo", "after_trial": 2,
                  "feedback": "A different comparison is warranted.",
                  "reflection": "A different comparison is warranted.",
                  "contract": {"summary": "A different comparison is warranted.", **fields}})
    assert expected in render_focus(state)
    state.update({"type": "model_call_started", "run_id": "magic-demo", "role": "researcher"})
    rendered = render_focus(state)
    assert expected in rendered and "after trial 2" in rendered
    assert "Expected: Validation AUC" not in rendered
    # A new experiment replaces the previous advice in the main narrative.
    state.update({"type": "trial_started", "run_id": "magic-demo", "trial_id": 3,
                  "config": {"model": "random_forest"},
                  "intent": {"hypothesis": "Shallower trees may generalize better."}})
    assert "Shallower trees may generalize better." in render_focus(state)
    assert expected not in render_focus(state)


@pytest.mark.parametrize('kind,field', [('review', 'recommendation'), ('reflection', 'next_comparison')])
def test_focus_renders_structured_candidate_as_readable_guidance(kind, field):
    state = structured_focus()
    state.update({'type': kind, 'run_id': 'magic-demo', 'after_trial': 2,
                  'feedback': 'Compare a shallower forest.', 'reflection': 'Compare a shallower forest.',
                  'contract': {'summary': 'Compare a shallower forest.',
                               field: {'model': 'random_forest', 'preprocessing': 'none',
                                       'params': {'max_depth': 8}}}})
    rendered = render_focus(state, height=32)
    assert 'Suggested next test:' in rendered
    assert 'random forest' in rendered and 'max_depth=8' in rendered
    assert 'none preprocessing' in rendered
    assert "{'model':" not in rendered


def test_focus_preserves_whole_explanation_before_cpu_on_small_screen():
    rendered = render_focus(structured_focus(), width=55, height=20)
    prose = " ".join(line.strip("│ ") for line in rendered.splitlines())
    assert "More trees may reduce prediction variance." in prose
    assert "0.91000" in rendered and "known" in rendered and "3:00" in rendered
    assert len(rendered.splitlines()) <= 20


def test_focus_run_reset_discards_guidance_and_timer():
    state = structured_focus()
    state.update({"type": "review", "run_id": "magic-demo", "after_trial": 2,
                  "feedback": "Try a smaller forest.", "contract": {"summary": "Try a smaller forest."}})
    state.update({"type": "run_started", "run_id": "next-run", "config": {}})
    assert state.lab.guidance is None and state.lab.phase_started is None


def test_focus_long_hypothesis_uses_complete_summary_and_ignores_rejected_advice():
    state = structured_focus()
    state.lab.intent["hypothesis"] = "A very long explanation " * 30 + "."
    state.update({"type": "supervisor_contract", "run_id": "magic-demo", "after_trial": 1,
                  "valid": False, "errors": ["Missing evidence."],
                  "contract": {"summary": "Unsupported advice must stay out of the narrative."}})
    rendered = render_focus(state)
    assert "Agent summary: Test a larger forest." in rendered
    assert "A very long explanation" not in rendered
    assert "Unsupported advice" not in rendered
    assert "…" not in rendered


def test_focus_call_timer_restarts_on_retry_and_stops_after_response(monkeypatch):
    state = structured_focus()
    for start in (130, 150):
        state.update({"type": "model_call_started", "run_id": "magic-demo", "role": "researcher",
                      "elapsed_seconds": start})
    monkeypatch.setattr("study.terminal.elapsed_now", lambda state: 155)
    assert "API response pending · 0:05 elapsed" in render_focus(state)
    state.update({"type": "model_call", "run_id": "magic-demo", "role": "researcher",
                  "status": "ok", "elapsed_seconds": 155})
    assert "API response pending" not in render_focus(state)


def test_focus_long_advice_falls_back_to_its_own_summary():
    state = structured_focus()
    state.update({"type": "review", "run_id": "magic-demo", "after_trial": 2,
                  "feedback": "Try a shallower forest.", "contract": {
                      "summary": "Try a shallower forest.",
                      "assessment": "A very long assessment " * 30 + ".",
                      "recommendation": "A very long recommendation " * 30 + "."}})
    rendered = render_focus(state)
    assert "Try a shallower forest." in rendered
    assert "Test a larger forest." not in rendered


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
    assert "0.80000" in rendered and "rmse" in rendered and "known" in rendered


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
        assert not display.focus and display.live is original_live
        frame = stream.getvalue()[offset:]
        assert "Live log" in frame and "FOCUS" not in frame
        assert "\x1b[2J" not in frame and "\x1b[2K" not in frame
        os.write(master, b"f")
        display.draw(state, detailed=True)
        assert display.focus and display.live is original_live
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
        until(b"FOCUS")
        os.write(master, b"l")
        until(b"Live log")
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
    assert "0.91000" in rendered
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
        assert 'VISIBLE_LOG_LINE' not in stream.getvalue()
        os.write(master, b'l')
        display.draw(state, detailed=True)
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


def test_focus_default_chart_and_axis_navigation_are_stable_across_parallel_runs(monkeypatch, keyboard_pty):
    from study.terminal import StatusLine
    from test_terminal import Terminal
    from test_live_chart import started, result, account
    master, _, stream = keyboard_pty
    monkeypatch.setenv('TERM', 'xterm')
    display = StatusLine(Terminal(), input_stream=stream)
    display.console.size = (96, 30)
    first = started()
    result(first,1,.8,10,account())
    second = started()
    second.run_id = 'second'
    states = {first.run_id:first, second.run_id:second}
    try:
        display.draw(first, detailed=True, states=states)
        live = display.live
        assert display.focus and display.selected_run == first.run_id
        assert 'Elapsed time' in display.stream.getvalue()
        display.draw(second, detailed=True, states=states)
        assert display.selected_run == first.run_id
        os.write(master,b'x')
        display.draw(first,detailed=True,states=states)
        assert display.chart_axis == 'cost'
        os.write(master,b']')
        selected = display.draw(first,detailed=True,states=states)
        assert selected is second and display.selected_run == 'second'
        os.write(master,b'\x1b[200~[x\x1b[201~')
        display.draw(first,detailed=True,states=states)
        assert display.selected_run == 'second' and display.chart_axis == 'cost'
        second.stopped = True
        display.draw(first,detailed=True,states=states)
        assert display.live is live and display.selected_run == 'second'
        os.write(master,b'[')
        assert display.draw(second,detailed=True,states=states) is first
    finally:
        display.clear()


def test_focus_chart_is_main_visual_and_small_terminal_keeps_facts():
    from test_live_chart import started, result, account
    state = started()
    result(state,1,.8,20,account())
    rendered = render_focus(state, width=80,height=24)
    assert 'Validation accuracy' in rendered and 'Elapsed time' in rendered
    assert '80.00%' in rendered and '85.00%' in rendered and '5.00 pp' in rendered
    compact = render_focus(state,width=40,height=14)
    assert 'Elapsed time' not in compact
    assert '80.00%' in compact and '$0.2000' in compact
    assert len(compact.splitlines()) <= 14


def test_tiny_focus_retains_trial_counts_and_unknown_cost_warning_before_secondary_detail():
    from test_live_lessons import lesson
    state = structured_focus()
    state.config['lesson_memory'] = True
    state.update(dict(type='lesson_memory',run_id=state.run_id,role='supervisor', lessons=[lesson(
        summary='The larger forest did not improve the validation result.',
        evidence=[{'trial_id':i,'metric':'roc_auc','split':'validation','value':.91} for i in range(11,17)])]))
    rendered = render_focus(state,width=40,height=14)
    prose = ' '.join(line.strip('│ ') for line in rendered.splitlines())
    assert 'Trials 1/12' in prose and '0 unsuccessful' in prose
    assert 'API total is incomplete; only known charges are shown.' in prose
    assert '$0.2400 known' in prose and '0.91000' in prose
    assert len(rendered.splitlines()) <= 14
