import copy
import io

import pytest
from rich.cells import cell_len
from rich.console import Console

from study.findings import Findings
from study.terminal import dashboard


def lesson(identity="forest", **updates):
    return {"id": identity, "status": "supported",
            "summary": "More trees did not improve validation AUC.",
            "scope": "This applies to the current split only.",
            "evidence": [{"trial_id": 1, "metric": "roc_auc", "split": "validation", "value": .93}],
            **updates}


def emit(state, kind, **values):
    state.update({"type": kind, "run_id": "lessons-demo", "elapsed_seconds": 20, **values})


def state():
    result = Findings()
    emit(result, "run_started", config={"lesson_memory": True, "allowance_seconds": 300,
        "trial_cap": 12, "dollar_cap": 3})
    emit(result, "model_call", role="supervisor", status="completed")
    result.best = {"trial_id": 1, "score": .93}
    result.accounting = {"known_cost": .2, "cost_complete": False}
    return result


def render(result, width=80, height=24, **options):
    stream = io.StringIO()
    Console(file=stream, width=width, height=height, color_system=None).print(
        dashboard(result, width=width, height=height, **options))
    return stream.getvalue()


def test_lesson_snapshots_track_actual_changes_without_mutation_or_duplicates():
    result = state()
    original = lesson()
    emit(result, "lesson_memory", lessons=[original])
    assert result.lessons.latest["change"] == "New"
    assert result.lessons.latest["source"] == "supervisor"
    original["summary"] = "Mutated outside the UI."
    assert result.lessons.latest["lesson"]["summary"] != original["summary"]
    emit(result, "lesson_memory", lessons=[lesson()])
    assert result.lessons.latest["revision"] == 1
    emit(result, "model_call", role="reflection", status="completed")
    emit(result, "lesson_memory", lessons=[lesson(status="inconclusive")])
    assert result.lessons.latest["change"] == "Updated"
    assert result.lessons.latest["revision"] == 2
    assert result.lessons.latest["source"] == "reflection"
    emit(result, "lesson_memory", lessons=[lesson(status="superseded")])
    assert result.lessons.latest["change"] == "Superseded"
    assert len(result.lessons.entries) == 1


def test_lessons_ignore_rejected_contracts_and_reset_or_evict_with_memory():
    result = state()
    emit(result, "supervisor_contract", valid=False, contract={"lesson_updates": [lesson()]}, errors=[])
    assert result.lessons.latest is None
    emit(result, "lesson_memory", lessons=[lesson("first"), lesson("second")])
    emit(result, "lesson_memory", lessons=[lesson("first")])
    assert len(result.lessons.entries) == 1
    assert result.lessons.latest["lesson"]["id"] == "first"
    emit(result, "run_started", config={})
    assert not result.lessons.entries


@pytest.mark.parametrize("focus,logs,width,height", [
    (True, False, 80, 24), (True, False, 40, 16),
    (False, False, 120, 38), (False, True, 80, 24), (False, True, 160, 40),
])
def test_lessons_are_live_in_focus_and_details_without_hiding_budgets(focus, logs, width, height):
    result = state()
    emit(result, "lesson_memory", lessons=[lesson()])
    output = render(result, width, height, focus=focus, logs=logs)
    prose = " ".join(line.strip("│ ") for line in output.splitlines())
    assert "Lessons" in output and "New" in output
    assert "More trees did not improve validation AUC." in prose
    assert "trial 1" in output and "supported" in output
    assert "0.93000" in output and "known" in output
    if logs:
        assert "Live log" in output
    assert len(output.splitlines()) <= height
    assert all(cell_len(line) <= width for line in output.splitlines())


def test_lesson_revisions_replace_old_takeaway_and_preserve_complete_literal_prose():
    result = state()
    emit(result, "lesson_memory", lessons=[lesson()])
    emit(result, "lesson_memory", lessons=[lesson(summary="The [red]forest[/red] needs more evidence.\x1b[2J")])
    for focus in (True, False):
        output = render(result, width=120, height=38, focus=focus)
        assert "Updated" in output and "The [red]forest[/red] needs more evidence." in output
        assert "More trees did not improve" not in output
        assert "\x1b" not in output and "…" not in output


def test_memory_waiting_and_disabled_states_do_not_invent_lessons():
    result = state()
    assert "No lessons recorded yet." in render(result, focus=True)
    result.config["lesson_memory"] = False
    assert "Lessons" not in render(result, focus=True)


def test_replayed_lessons_match_live_updates_and_newest_revision_is_first():
    result = state()
    snapshots = [[lesson("one")], [lesson("one"), lesson("two")],
                 [lesson("two"), lesson("one", summary="A later comparison changed the finding.")]]
    for snapshot in snapshots:
        emit(result, "lesson_memory", lessons=snapshot)
    other = state()
    for snapshot in copy.deepcopy(snapshots):
        emit(other, "lesson_memory", lessons=snapshot)
    assert other.lessons.entries == result.lessons.entries
    assert result.lessons.latest["lesson"]["id"] == "one"
    output = render(result, width=120, height=45)
    assert output.index("A later comparison changed") < output.index("More trees did not improve")


def test_long_lesson_never_clips_sentences_or_displaces_focus_budgets():
    from test_focus import structured_focus
    result = structured_focus()
    result.config['lesson_memory'] = True
    summary = ('A larger forest showed no measurable improvement over the smaller baseline on this '
               'validation split, so further comparisons should test alternative settings before '
               'treating increased model capacity as a reliable improvement.')
    emit(result, 'lesson_memory', lessons=[lesson(summary=summary)])
    for width, height in [(80,24), (40,16)]:
        output = render(result, width, height, focus=True)
        prose = ' '.join(line.strip('│ ') for line in output.splitlines())
        assert 'Lessons' in output and '0.91000' in output and 'known' in output
        assert 'API total is incomplete;' in output
        if width == 80:
            assert summary in prose
        else:
            assert 'Full lesson saved in lessons.json.' in prose
        assert len(output.splitlines()) <= height and '…' not in output


@pytest.mark.parametrize('width,height,logs', [(80,24,False), (120,34,True), (120,38,True), (160,40,True)])
def test_lessons_preserve_recent_experiment_table_when_it_previously_fitted(width,height,logs):
    from test_dashboard import sample
    result = sample()
    result.config['lesson_memory'] = True
    emit(result, 'lesson_memory', lessons=[lesson()])
    output = render(result, width, height, logs=logs)
    assert 'Recent experiments' in output and 'Gap' in output
    assert 'Lessons' in output
    if logs:
        assert 'Live log' in output
    assert len(output.splitlines()) <= height


def test_full_notebook_link_remains_when_scope_fills_the_lesson_panel():
    result = state()
    emit(result, 'lesson_memory', lessons=[lesson(str(i)) for i in range(6)])
    assert 'lessons.json' in render(result, width=120, height=42)
