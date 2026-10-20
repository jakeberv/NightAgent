import asyncio
import io
import json

from study.config import StudyConfig
from study.fake import FakeModel
from study.controller import run_one


def test_live_progress_matches_durable_trace_and_usage(tmp_path):
    from study.progress import ConsoleProgress
    stream = io.StringIO()
    async def trial(*args, **kwargs):
        return {"status": "completed", "validation_auc": .94,
                "artifact": "fixture.joblib", "artifact_hash": "fixture"}
    run = tmp_path / "run"
    result = asyncio.run(run_one(
        StudyConfig(condition="periodic_reflection", trial_cap=4), tmp_path, run,
        FakeModel(), trial_runner=trial, project={}, progress=ConsoleProgress(stream=stream, verbose=True)))
    output = stream.getvalue()
    assert "periodic_reflection" in output
    assert "researcher" in output and "supervisor" in output and "reflection" in output
    assert "trial 4" in output and "0.940000" in output
    assert "trial_cap" in output and "USD" in output
    assert "input=800" in output and "output=240" in output
    assert result["accounting"]["calls"] == 8
    events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    completed = [event for event in events if event["type"] == "model_call"]
    assert completed[-1]["accounting"]["input_tokens"] == 800
    assert completed[-1]["accounting"]["output_tokens"] == 240
    log = (run / "progress.log").read_text()
    assert "trial 4" in log and "trial_cap" in log
    assert "The scripted agent is comparing model capacity" in log


def test_unknown_usage_is_labelled_and_token_subsets_are_separate():
    from study.progress import ConsoleProgress
    from study.events import Accounting
    stream = io.StringIO()
    accounting = Accounting()
    accounting.add({"cost": .12, "prompt_tokens": 100, "completion_tokens": 20,
                   "prompt_tokens_details": {"cached_tokens": 60},
                   "completion_tokens_details": {"reasoning_tokens": 5}})
    accounting.add(None)
    ConsoleProgress(stream=stream, verbose=True)({"type": "model_call", "run_id": "r",
        "elapsed_seconds": 3, "role": "supervisor", "status": "failed",
        "error": "ProviderError", "accounting": accounting.snapshot()})
    text = stream.getvalue()
    assert "known USD=0.120000" in text and "incomplete" in text
    assert "input=100" in text and "output=20" in text
    assert "cached=60" in text and "reasoning=5" in text


def test_verbose_outputs_full_messages_and_broken_terminal_does_not_stop_run():
    from study.progress import ConsoleProgress
    event = {"type": "model_call", "run_id": "r", "elapsed_seconds": 1,
             "role": "researcher", "status": "completed",
             "response": {"message": {"content": "long " * 1000 + "END_OF_MESSAGE"}}}
    normal, verbose = io.StringIO(), io.StringIO()
    ConsoleProgress(stream=normal)(event)
    ConsoleProgress(stream=verbose, verbose=True)(event)
    assert "END_OF_MESSAGE" not in normal.getvalue()
    assert "END_OF_MESSAGE" in verbose.getvalue()
    class ClosedPipe:
        def write(self, text):
            raise BrokenPipeError()
    ConsoleProgress(stream=ClosedPipe(), verbose=True)(event)


def test_terminal_control_characters_cannot_modify_display():
    from study.progress import ConsoleProgress
    stream = io.StringIO()
    ConsoleProgress(stream=stream, verbose=True)({"type": "reflection", "run_id": "r",
        "elapsed_seconds": 1, "reflection": "\x1b[2Jbad\rspoof"})
    assert "\x1b" not in stream.getvalue() and "\r" not in stream.getvalue()


def test_journal_keeps_readable_log_without_terminal_observer(tmp_path):
    from study.events import Journal
    import time
    Journal(tmp_path, time.monotonic()).emit("failure", error="fixture failed")
    assert "fixture failed" in (tmp_path / "progress.log").read_text()
