"""The lab display describes recorded actions, never invented agent reasoning."""
import io

import pytest
from rich.console import Console

from study.findings import Findings
from study.terminal import dashboard


def emit(state, kind, **data):
    state.update(dict(type=kind, run_id="lab", elapsed_seconds=10, **data))


def start(direction="maximize"):
    state = Findings()
    emit(state, "run_started", config={"condition": "periodic_reflection", "allowance_seconds": 300},
         problem={"id": "MAGIC", "evaluation": {"objective": {"metric": "auc", "direction": direction}},
                  "targets": [{"name": "goal", "value": .9}]})
    return state


def finish(state, trial, score, config=None, status="completed"):
    emit(state, "trial_finished", result=dict(trial_id=trial, score=score, status=status, config=config or {}))


def test_roles_are_event_driven_and_stop_on_failures():
    state = start()
    emit(state, "model_call_started", role="reflection")
    assert state.lab.role == "reflection" and state.lab.busy
    emit(state, "model_call", role="reflection", status="failed")
    assert not state.lab.busy
    emit(state, "model_call_started", role="researcher")
    emit(state, "tool_call", role="researcher", name="search_literature")
    assert state.lab.role == "researcher" and "search_literature" in state.lab.action
    emit(state, "trial_started", trial_id=2, config={"model": "ridge"})
    assert state.lab.role == "local" and state.lab.busy
    emit(state, "resources", waiting=True, max_cores=4, active_cores=4, allocated_cores=0)
    assert "Waiting" in state.lab.action
    emit(state, "run_stopped", summary={"stop_reason": "deadline"})
    assert not state.lab.busy


def test_experiment_uses_actual_config_and_named_previous_completed_comparison():
    state = start()
    finish(state, 1, .8, {"model": "random_forest", "params": {"n_estimators": 100, "max_depth": None}})
    finish(state, 2, None, status="failed")
    emit(state, "decision", trial_id=3, message={"content": "## Rationale\nTest more trees. The [red]literal[/red] is safe.\x1b[2J"})
    emit(state, "trial_started", trial_id=3, config={"model": "random_forest", "params": {"n_estimators": 200}})
    assert state.lab.comparison == 1
    assert "n_estimators: 100 -> 200" in state.lab.changes
    assert "max_depth: null -> (default)" in state.lab.changes
    assert "Test more trees" in state.lab.rationale
    output = io.StringIO()
    Console(file=output, width=120, height=40, color_system=None).print(dashboard(state, width=120, height=40))
    assert "completed trial 1" in output.getvalue()
    assert "Agent interpretation" in output.getvalue()
    assert "[red]literal[/red]" in output.getvalue() and "\x1b" not in output.getvalue()
    emit(state, "trial_started", trial_id=4, config={})
    assert not state.lab.rationale  # No stale rationale on a missing decision.


@pytest.mark.parametrize("direction,scores", [("maximize", [.8, .91, .91]), ("minimize", [.95, .89, .89])])
def test_discoveries_only_celebrate_measured_improvements(direction, scores):
    state = start(direction)
    for trial, score in enumerate(scores, 1):
        finish(state, trial, score)
        emit(state, "selection", best={"trial_id": min(trial, 2), "score": score})
    messages = [d["message"] for d in state.lab.discoveries]
    assert sum("has been reached" in m for m in messages) == 1
    assert sum("new best" in m for m in messages) == 2
    assert any("tied" in m for m in messages)
    before = len(messages)
    emit(state, "selection", best={"trial_id": 2, "score": scores[1]})
    assert len(state.lab.discoveries) == before
    finish(state, 4, None, status="timeout")
    assert "timeout" in state.lab.discoveries[-1]["message"]
    emit(state, "run_started", config={})
    assert not state.lab.discoveries and not state.lab.rationale


def test_rationale_is_bounded_and_raw_responses_are_not_displayed():
    state = start()
    emit(state, "model_call", role="researcher", status="completed", response={"message": {"content": "PRIVATE_RAW"}})
    assert not state.lab.rationale
    emit(state, "decision", trial_id=1, message={"content": "a" * 10000})
    emit(state, "trial_started", trial_id=1, config={})
    assert len(state.lab.rationale) <= 240


def test_rationale_prefers_bold_heading_and_does_not_keep_following_section():
    from study.lab import sentence_summary
    assert sentence_summary('Intro\n\n**Rationale:**\nTry more trees.\n## Next\nOther') == 'Try more trees.'


def test_avatars_animate_only_during_recorded_activity_and_disabled_roles_are_labeled():
    from study.terminal import role_strip
    state = start()
    def render(elapsed):
        stream = io.StringIO()
        Console(file=stream, width=110, color_system=None).print(role_strip(state, expanded=True, elapsed=elapsed))
        return stream.getvalue()
    emit(state, "model_call_started", role="reflection")
    assert render(0) != render(.5)
    assert "[-~-]" in render(.5)
    emit(state, "model_call", role="reflection", status="completed")
    assert render(0) == render(.5)
    emit(state, "run_started", config={"condition": "researcher_alone"})
    assert render(0).count("Off in this condition") == 2


@pytest.mark.parametrize("width,height", [(76,32), (100,32), (100,34), (120,38)])
def test_lab_layout_preserves_notebook_metrics_and_discoveries(width, height):
    state = start()
    finish(state, 1, .91)
    emit(state, "selection", best={"trial_id": 1, "score": .91})
    emit(state, "decision", trial_id=2, message={"content": "Try a second model."})
    emit(state, "trial_started", trial_id=2, config={"model": "random_forest"})
    stream = io.StringIO()
    Console(file=stream, width=width, height=height, color_system=None).print(dashboard(state, width=width, height=height))
    rendered = stream.getvalue()
    assert "Agent interpretation" in rendered and "Try a second model." in rendered
    assert "Host CPU" in rendered and "Tokens" in rendered and "0.91000" in rendered
    assert "has been reached" in rendered and "Trail" in rendered
    assert "Observed:" in rendered
    assert len(rendered.splitlines()) == height


def test_trial_trail_keeps_newest_outcomes_when_ids_grow():
    from study.terminal import trial_trail
    state = start()
    for trial in range(100, 112):
        finish(state, trial, .9)
        emit(state, "selection", best={"trial_id": 100, "score": .9})
    rendered = trial_trail(state, 72)
    assert "111" in rendered.plain and "100" not in rendered.plain
    assert rendered.cell_len <= 72
