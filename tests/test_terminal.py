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
            await asyncio.sleep(.35)
            assert stream.getvalue().count("\r\x1b[2K") >= 2
            assert "researcher API" in stream.getvalue()
            assert "0 ok" in stream.getvalue()
            assert "5:00" in stream.getvalue()
    asyncio.run(scenario())
    assert stream.getvalue().endswith("\r\x1b[2K")


def test_animation_never_emits_control_codes_to_pipes_or_when_disabled(monkeypatch):
    monkeypatch.setenv("TERM", "xterm-256color")
    async def scenario(stream, animate):
        async with ConsoleProgress(stream=stream, animate=animate) as progress:
            progress(started())
            await asyncio.sleep(.15)
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
    assert "\r\x1b[2KA readable log entry\n" in stream.getvalue()


def test_default_panel_replaces_itself_and_hides_raw_model_content(monkeypatch):
    monkeypatch.setenv("TERM", "xterm")
    stream = Terminal()
    async def scenario():
        async with ConsoleProgress(stream=stream) as progress:
            progress(started())
            progress({"type": "model_call", "run_id": "pilot", "elapsed_seconds": 1,
                "role": "researcher", "status": "completed",
                "response": {"message": {"content": "RAW_MODEL_CONTENT"}}})
            await asyncio.sleep(.25)
        text = stream.getvalue()
        assert "RAW_MODEL_CONTENT" not in text
        assert "FINDINGS" in text and "\x1b[1A" in text
        assert "No selected model yet" in text
    asyncio.run(scenario())


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
            await asyncio.sleep(.15)
            progress({"type": "run_stopped", "run_id": "pilot", "elapsed_seconds": 2,
                "summary": {"stop_reason": "trial_cap", "best": None, "accounting": {}}})
            assert progress.display.visible_rows == 0
            stream.write('{"final_stdout":"must survive"}\n')
        assert stream.getvalue().endswith('{"final_stdout":"must survive"}\n')
    asyncio.run(scenario())
