import asyncio
import io

from study.progress import ConsoleProgress


class Terminal(io.StringIO):
    def isatty(self):
        return True


def started():
    return {"type": "run_started", "run_id": "pilot", "elapsed_seconds": 0,
        "config": {"condition": "pilot", "model": "fixture", "provider": "fixture",
                   "allowance_seconds": 300, "trial_cap": 12, "dollar_cap": 3}}


def test_interactive_status_animates_without_new_events_and_clears_on_exit(monkeypatch):
    monkeypatch.setenv("TERM", "xterm-256color")
    stream = Terminal()
    async def scenario():
        async with ConsoleProgress(stream=stream, summary_interval=0) as progress:
            progress(started())
            progress({"type": "model_call_started", "role": "researcher",
                      "run_id": "pilot", "elapsed_seconds": 1})
            await asyncio.sleep(.65)
            assert stream.getvalue().count("\x1b[H") >= 2
            assert "researcher API" in stream.getvalue()
            assert "0 ok" in stream.getvalue()
            assert "5:00" in stream.getvalue()
            assert "⠋" in stream.getvalue()
            assert any(frame in stream.getvalue() for frame in "⠙⠹⠸⠼⠴⠦⠧⠇⠏")
    asyncio.run(scenario())
    assert "\x1b[?25h" in stream.getvalue()
    assert stream.getvalue().endswith("\x1b[?1049l")


def test_animation_never_emits_control_codes_to_pipes_or_when_disabled(monkeypatch):
    monkeypatch.setenv("TERM", "xterm-256color")
    async def scenario(stream, animate):
        async with ConsoleProgress(stream=stream, animate=animate) as progress:
            progress(started())
            await asyncio.sleep(.35)
        assert "\x1b" not in stream.getvalue()
    asyncio.run(scenario(io.StringIO(), True))
    asyncio.run(scenario(Terminal(), False))
    monkeypatch.setenv("TERM", "dumb")
    asyncio.run(scenario(Terminal(), True))


def test_log_lines_clear_animation_before_printing(monkeypatch):
    from study.terminal import StatusLine
    from study.findings import Findings
    monkeypatch.setenv("TERM", "xterm")
    stream = Terminal()
    status = StatusLine(stream)
    state = Findings()
    state.update(started())
    status.draw(state)
    status.write("A readable log entry")
    assert "\x1b[2KA readable log entry\n" in stream.getvalue()
    assert status.live is None


def test_default_panel_replaces_itself_and_shows_full_model_log(monkeypatch):
    monkeypatch.setenv("TERM", "xterm")
    stream = Terminal()
    async def scenario():
        async with ConsoleProgress(stream=stream) as progress:
            progress(started())
            progress({"type": "model_call", "run_id": "pilot", "elapsed_seconds": 1,
                "role": "researcher", "status": "completed",
                "response": {"message": {"content": "RAW_MODEL_CONTENT"}}})
            await asyncio.sleep(.35)
        text = stream.getvalue()
        assert "RAW_MODEL_CONTENT" in text
        assert "Live log" in text and "\x1b[H" in text
        assert "No selected model yet" in text
    asyncio.run(scenario())


def test_dashboard_refresh_does_not_erase_screen_before_repainting(monkeypatch):
    from study.terminal import StatusLine
    from study.findings import Findings
    monkeypatch.setenv("TERM", "xterm-256color")
    stream = Terminal()
    status = StatusLine(stream)
    status.console.size = (100, 30)
    state = Findings()
    state.update(started())
    try:
        status.draw(state, detailed=True)
        first = len(stream.getvalue())
        state.activity = "new activity"
        status.draw(state, detailed=True)
        refresh = stream.getvalue()[first:]
        assert "new activity" in refresh
        assert "\x1b[2K" not in refresh  # No clear-line pass before the new frame.
        assert "\x1b[2J" not in refresh  # No clear-screen pass either.
        assert "\x1b[H" in refresh
        # Resize to the compact view; screen padding replaces stale dashboard rows.
        status.console.size = (45, 15)
        status.draw(state, detailed=True)
    finally:
        status.clear()
    status.write("Final output survives")
    output = stream.getvalue()
    assert output.count("\x1b[?1049h") == output.count("\x1b[?1049l") == 1
    assert output.rfind("\x1b[?1049l") < output.index("Final output survives")


def test_dashboard_restores_normal_screen_when_context_is_interrupted(monkeypatch):
    import pytest
    monkeypatch.setenv("TERM", "xterm-256color")
    stream = Terminal()
    async def scenario():
        with pytest.raises(asyncio.CancelledError):
            async with ConsoleProgress(stream=stream, summary_interval=0) as progress:
                progress(started())
                progress.display.draw(progress.findings, detailed=True)
                raise asyncio.CancelledError()
    asyncio.run(scenario())
    assert "\x1b[?1049h" in stream.getvalue()
    assert stream.getvalue().endswith("\x1b[?25h\x1b[?1049l")


def test_verbose_opt_in_prints_model_content_without_changing_trace_format():
    stream = io.StringIO()
    ConsoleProgress(stream=stream, verbose=True)({"type": "model_call",
        "run_id": "pilot", "elapsed_seconds": 1, "role": "researcher", "status": "completed",
        "response": {"message": {"content": "RAW_MODEL_CONTENT"}}})
    assert "RAW_MODEL_CONTENT" in stream.getvalue()


def test_stop_clears_panel_before_final_stdout_even_with_summaries_disabled(monkeypatch):
    monkeypatch.setenv("TERM", "xterm")
    stream = Terminal()
    async def scenario():
        async with ConsoleProgress(stream=stream, summary_interval=0) as progress:
            progress(started())
            await asyncio.sleep(.35)
            progress({"type": "run_stopped", "run_id": "pilot", "elapsed_seconds": 2,
                "summary": {"stop_reason": "trial_cap", "best": None, "accounting": {}}})
            assert progress.display.live is None
            stream.write('{"final_stdout":"must survive"}\n')
        assert stream.getvalue().endswith('{"final_stdout":"must survive"}\n')
    asyncio.run(scenario())
