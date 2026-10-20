import io

import pytest
from rich.console import Console

from study.findings import Findings


def sample(direction="maximize"):
    state = Findings()
    def emit(kind, **payload):
        state.update({"type": kind, "run_id": "magic-pilot", "elapsed_seconds": 134, **payload})
    emit("run_started", config={"allowance_seconds": 300, "trial_cap": 12, "dollar_cap": 3},
         problem={"id": "MAGIC", "evaluation": {"objective": {"metric": "roc_auc", "direction": direction}},
                  "targets": [{"name": "milestone", "value": .93}, {"name": "stretch", "value": .95}]})
    scores = [.931, .933, .932] if direction == "maximize" else [.933, .931, .932]
    for trial, score in enumerate(scores, 1):
        emit("trial_finished", result={"trial_id": trial, "status": "completed", "score": score,
             "config": {"model": "histogram_gradient_boosting", "preprocessing": "standard", "params": {"max_iter": 200}}})
        best = min(trial, 2)
        emit("selection", best={"trial_id": best, "score": scores[best - 1]})
    emit("model_call", role="researcher", status="completed", accounting={"known_cost": .24,
         "cost_complete": False, "input_tokens": 1000, "output_tokens": 100,
         "token_usage_complete": True})
    emit("model_call_started", role="researcher")
    return state


@pytest.mark.parametrize("width,height", [(120, 38), (80, 24), (55, 28), (40, 12)])
def test_dashboard_fits_terminal_and_preserves_critical_information(width, height):
    from study.terminal import dashboard
    from rich.cells import cell_len
    stream = io.StringIO()
    console = Console(file=stream, width=width, height=height, color_system=None)
    console.print(dashboard(sample(), width=width, height=height))
    output = stream.getvalue()
    assert "0.933" in output and "known" in output and "0.24" in output
    assert "researcher" in output
    assert len(output.splitlines()) <= height
    assert all(cell_len(line) <= width for line in output.splitlines())
    if height >= 24:
        assert "Recent experiments" in output
        assert "Trial scores" in output
        assert "Best so far" in output


def test_trial_history_and_outcomes_support_minimization_and_reset():
    state = sample("minimize")
    assert [row["outcome"] for row in state.recent] == ["New best", "New best", "Not best"]
    assert [row["best"] for row in state.history] == [.933, .931, .931]
    state.update({"type": "run_started", "run_id": "next", "config": {}})
    assert not state.recent and not state.history


def test_chart_labels_bounds_and_never_invents_missing_scores():
    from study.terminal import score_chart
    state = sample()
    state.update({"type": "trial_finished", "run_id": "magic-pilot", "result": {
        "trial_id": 4, "status": "timeout"}})
    stream = io.StringIO()
    Console(file=stream, width=100, color_system=None).print(score_chart(state, 80))
    text = stream.getvalue()
    assert "0.93100" in text and "0.93300" in text
    assert "Trial scores" in text and "Best so far" in text
    assert state.recent[-1]["score"] is None


def test_untrusted_model_text_remains_literal_in_rich():
    from study.terminal import dashboard
    state = sample()
    state.review = (3, "[red]literal[/red]\x1b[2J")
    stream = io.StringIO()
    Console(file=stream, width=120, height=40, color_system=None).print(dashboard(state, width=120, height=40))
    output = stream.getvalue()
    assert "[red]literal[/red]" in output and "\x1b" not in output
