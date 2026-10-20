import asyncio
import io
import json

import pytest


def event(kind, **payload):
    return {"type": kind, "run_id": "pilot", "elapsed_seconds": 12, **payload}


@pytest.mark.parametrize("direction,scores,target", [
    ("maximize", [.91, .94, .93], .93), ("minimize", [20, 10, 15], 12),
])
def test_findings_report_observed_best_improvement_failures_and_targets(direction, scores, target):
    from study.findings import Findings
    state = Findings()
    state.update(event("run_started", problem={"evaluation": {"objective": {
        "metric": "score", "direction": direction}}, "targets": [{"name": "goal", "value": target}]}))
    for trial, score in enumerate(scores, 1):
        state.update(event("trial_finished", result={"trial_id": trial, "status": "completed",
            "score": score, "config": {"model": "tree", "preprocessing": "none"}}))
    state.update(event("trial_finished", result={"trial_id": 4, "status": "timeout"}))
    state.update(event("selection", best={"trial_id": 2, "score": scores[1]},
                       target_selections={"goal": {"trial_id": 2}}))
    state.update(event("review", after_trial=3, feedback="Try a linear baseline.\x1b[2J"))
    state.update(event("model_call", status="failed", role="researcher",
                       accounting={"known_cost": .1, "cost_complete": False}))
    text = state.render()
    assert "3 completed, 1 unsuccessful" in text
    assert f"{scores[1]:.6f}" in text and "trial 2" in text
    assert "goal reached" in text and "tree" in text
    assert "improvement" in text and "known USD=0.100000 (incomplete)" in text
    assert "Supervisor excerpt after trial 3" in text and "Try a linear baseline." in text
    assert "\x1b" not in text


def test_incremental_reader_keeps_partial_line_until_append(tmp_path):
    from study.findings import EventTail
    path = tmp_path / "events.jsonl"
    path.write_bytes((json.dumps(event("run_started")) + "\n").encode() + b'{"type":')
    with EventTail(path) as tail:
        assert [e["type"] for e in tail.read()] == ["run_started"]
        assert tail.read() == []
        with path.open("ab") as handle:
            handle.write(b'"reflection","run_id":"pilot","reflection":"caf\xc3')
        assert tail.read() == []
        with path.open("ab") as handle:
            handle.write(b'\xa9"}\n')
        assert tail.read()[0]["reflection"] == "caf\u00e9"


def test_summary_timer_runs_while_model_waits_and_suppresses_unchanged_snapshots():
    from study.progress import ConsoleProgress
    stream = io.StringIO()
    async def scenario():
        async with ConsoleProgress(stream=stream, summary_interval=.01) as progress:
            progress(event("run_started", config={"condition": "test", "model": "fixture",
                "provider": "fixture", "allowance_seconds": 60, "trial_cap": 4, "dollar_cap": 1}))
            progress(event("model_call_started", role="researcher"))
            await asyncio.sleep(.05)
            assert stream.getvalue().count("FINDINGS") == 1
            assert "researcher model call in progress" in stream.getvalue()
            await asyncio.sleep(.03)
            assert stream.getvalue().count("FINDINGS") == 1
    asyncio.run(scenario())


def test_watch_completed_run_is_read_only_and_exits_without_provider(tmp_path, monkeypatch, capsys):
    from study.__main__ import main
    import sys
    records = [event("run_started"), event("run_stopped", summary={
        "stop_reason": "trial_cap", "accounting": {}, "best": None})]
    path = tmp_path / "events.jsonl"
    original = "".join(json.dumps(e) + "\n" for e in records)
    path.write_text(original)
    monkeypatch.setattr(sys, "argv", ["study", "watch", "--output", str(tmp_path)])
    monkeypatch.setattr("study.__main__.live_model", lambda _: pytest.fail("watch called provider"))
    main()
    output = capsys.readouterr().out
    assert output.count("FINDINGS") == 1 and "stopped: trial_cap" in output
    assert path.read_text() == original
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("interval", ["0", "-1", "nan", "inf"])
def test_watch_rejects_invalid_interval(tmp_path, monkeypatch, capsys, interval):
    from study.__main__ import main
    import sys
    monkeypatch.setattr(sys, "argv", ["study", "watch", "--output", str(tmp_path),
                                    "--interval", interval])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert "Summary interval must be finite and positive" in capsys.readouterr().err


def test_final_summary_is_immediate_and_can_be_disabled():
    from study.progress import ConsoleProgress
    stopped = event("run_stopped", summary={"stop_reason": "deadline", "trials": 0,
        "training_seconds": 0, "accounting": {}, "best": None})
    for interval, count in [(15, 1), (0, 0)]:
        stream = io.StringIO()
        ConsoleProgress(stream=stream, summary_interval=interval)(stopped)
        assert stream.getvalue().count("FINDINGS") == count


def test_corrupt_complete_event_is_not_silently_ignored(tmp_path):
    from study.findings import EventTail
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"type": broken}\n')
    with EventTail(path) as tail, pytest.raises(ValueError, match="Corrupt complete event"):
        tail.read()


def test_watcher_follows_append_and_finishes_before_next_summary_interval(tmp_path):
    from study.findings import watch
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps(event("run_started")) + "\n")
    stream = io.StringIO()
    async def scenario():
        task = asyncio.create_task(watch(tmp_path, interval=60, stream=stream))
        await asyncio.sleep(.01)
        assert stream.getvalue().count("FINDINGS") == 1
        with path.open("a") as handle:
            handle.write(json.dumps(event("run_stopped", summary={
                "stop_reason": "trial_cap", "accounting": {}, "best": None})) + "\n")
        await asyncio.wait_for(task, timeout=3)
    asyncio.run(scenario())
    assert stream.getvalue().count("FINDINGS") == 2
    assert "stopped: trial_cap" in stream.getvalue()


@pytest.mark.parametrize("recover_after_attach", [False, True])
def test_watcher_exits_when_recovery_freezes_a_run_without_stop_event(tmp_path, recover_after_attach):
    from study.findings import watch
    from study.events import atomic_json
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps(event("run_started")) + "\n")
    stream = io.StringIO()
    def recover():
        atomic_json(tmp_path / "summary.json", {"stop_reason": "interrupted",
            "best": None, "accounting": {}})
    async def scenario():
        if not recover_after_attach:
            recover()
        task = asyncio.create_task(watch(tmp_path, interval=60, stream=stream))
        if recover_after_attach:
            await asyncio.sleep(.01)
            recover()
        await asyncio.wait_for(task, timeout=3)
    asyncio.run(scenario())
    assert "stopped: interrupted" in stream.getvalue()
