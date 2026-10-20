"""Measured progress, honest coordinates and terminal-size guarantees."""
import io
import math

import pytest
from rich.cells import cell_len
from rich.console import Console

from study.findings import Findings


def started(direction='maximize', metric='accuracy'):
    state = Findings()
    state.update(dict(type='run_started', run_id='chart-run', elapsed_seconds=0,
        config={'allowance_seconds': 300, 'dollar_cap': 3, 'trial_cap': 200},
        problem={'evaluation': {'objective': {'metric': metric, 'direction': direction}},
                 'targets': [{'name': 'goal', 'value': .85}]}))
    return state


def result(state, trial, score, elapsed, accounting=None, status='completed'):
    if accounting is not None:
        state.update(dict(type='model_call', run_id=state.run_id, status='ok', role='researcher',
                          elapsed_seconds=elapsed-1, accounting=accounting))
    state.update(dict(type='trial_finished', run_id=state.run_id, elapsed_seconds=elapsed,
        result={'trial_id': trial, 'status': status, 'score': score, 'config': {'model': 'logistic'}}))
    if status == 'completed' and isinstance(score, (int, float)) and math.isfinite(score):
        best = state.best
        if best is None or (score < best['score'] if state.objective['direction'] == 'minimize' else score > best['score']):
            best = {'trial_id': trial, 'score': score}
        state.update(dict(type='selection', run_id=state.run_id, elapsed_seconds=elapsed, best=best))


def account(cost=.2, tokens=120, complete=True):
    return dict(known_cost=cost, cost_complete=complete, token_usage_complete=complete,
                input_tokens=tokens-20, output_tokens=20, cached_tokens=40, reasoning_tokens=10)


def test_history_preserves_full_run_and_completion_accounting_snapshots():
    state = started()
    for trial in range(1, 102):
        result(state, trial, .8, trial*2, account(cost=trial/100, tokens=trial+100))
    assert len(state.history) == 101
    first = state.history[0]
    assert first['elapsed'] == 2 and first['cost'] == .01 and first['tokens'] == 101
    assert first['best'] == .8
    assert state.history[-1]['tokens'] == 201  # Cached/reasoning are subsets, not additions.


def test_missing_accounting_and_unsuccessful_trials_never_become_zero_scores():
    state = started()
    result(state, 1, .8, 10)
    result(state, 2, .7, 20, account(complete=False))
    result(state, 3, .99, 30, status='timeout')
    result(state, 4, float('nan'), 40)
    assert len(state.history) == 2
    assert all(p['cost'] is None and p['tokens'] is None for p in state.history)
    assert state.unsuccessful == 1


def test_plot_coordinates_use_actual_time_and_best_line_is_not_trial_interpolation():
    from study.live_chart import plot_data, raster
    state = started()
    for trial, score, elapsed in [(1,.8,10),(2,.84,100),(3,.81,110)]:
        result(state, trial, score, elapsed, account())
    data = plot_data(state, 'time')
    assert [p['x'] for p in data['points']] == [10,100,110]
    assert [p['best'] for p in data['points']] == [.8,.84,.84]
    grid = raster(data['points'], [], width=31, height=11, x_max=300, low=.75, high=.85, ascii_only=True)
    # Result 1 at x=1/y=5; result 2 x=10/y=1. A step stays flat until x=10.
    assert grid[5][1] == '*'
    assert all(grid[5][x] == '-' for x in range(2,10))
    assert grid[1][10] == '*'
    assert grid[4][11] == 'o'


@pytest.mark.parametrize('direction,scores', [('maximize',[.8,.84,.81,.84]),('minimize',[.9,.84,.88,.84])])
def test_plateau_is_observed_trials_not_convergence(direction, scores):
    from study.live_chart import progress_sentence
    state = started(direction)
    for trial, score in enumerate(scores,1):
        result(state, trial, score, trial*10)
    assert progress_sentence(state) == 'The best score has not improved in the last 2 trials.'


def render(state, **kwargs):
    from study.live_chart import chart
    width = kwargs.get('width', 70)
    out = io.StringIO()
    Console(file=out, width=width, color_system=None).print(chart(state, **kwargs))
    return out.getvalue()


@pytest.mark.parametrize('axis,label', [('time','Elapsed time'),('cost','Cumulative API cost'),('tokens','Cumulative API tokens')])
def test_axis_labels_targets_and_incomplete_accounting(axis, label):
    state = started()
    result(state,1,.8,10,account())
    result(state,2,.84,20,account(complete=False))
    output = render(state,width=70,height=10,axis=axis,ascii_only=True)
    assert label in output and 'target' in output.lower() and 'accuracy' in output
    if axis != 'time':
        assert 'incomplete' in output and '1 omitted' in output
    assert len(output.splitlines()) <= 10
    assert all(cell_len(line) <= 70 for line in output.splitlines())
    assert output.isascii()


def test_empty_single_equal_and_minimization_charts_have_finite_stable_bounds():
    from study.live_chart import plot_data
    state = started('minimize','rmse')
    assert 'Waiting for completed experiments.' in render(state,width=60,height=10)
    result(state,1,.8,10)
    first = plot_data(state,'time')
    assert first['low'] < .8 < first['high']
    result(state,2,.8,20)
    second = plot_data(state,'time')
    assert (first['low'],first['high']) == (second['low'],second['high'])
    assert 'lower is better' in render(state,width=60,height=10)


def test_chart_caches_idle_frames_but_updates_after_result_and_axis_change():
    from study.live_chart import chart
    state = started()
    result(state,1,.8,10,account())
    first = chart(state,width=70,height=10)
    state.elapsed = 15
    assert chart(state,width=70,height=10) is first
    assert chart(state,width=70,height=10,axis='cost') is not first
    result(state,2,.84,20,account())
    assert chart(state,width=70,height=10) is not first


def test_chart_retains_bounds_after_resize_and_new_run_resets_them():
    from study.live_chart import plot_data
    state = started()
    result(state,1,.1,10)
    before = plot_data(state,'time')
    result(state,2,.9,20)
    after = plot_data(state,'time')
    assert after['low'] <= before['low'] and after['high'] >= before['high']
    state.update(dict(type='run_started',run_id='next',config={}))
    assert state.chart_bounds is None and not state.history


def test_empty_targetless_chart_does_not_lock_placeholder_scale():
    from study.live_chart import chart, plot_data
    state = started(); state.targets = []
    chart(state,width=70,height=10)
    assert state.chart_bounds is None
    result(state,1,.81,10)
    data = plot_data(state,'time')
    assert .80 <= data['low'] < .81 < data['high'] <= .82


def test_small_auc_improvements_are_not_flattened_by_percentage_padding():
    from study.live_chart import plot_data
    state = started(metric='roc_auc'); state.targets = []
    result(state,1,.931,10)
    result(state,2,.933,20)
    data = plot_data(state,'time')
    assert data['high'] - data['low'] < .01
