import io

from rich.console import Console

from study.findings import Findings
from study.progress import format_event
from study.terminal import dashboard


def event(kind, **data):
    return dict(type=kind, run_id='pilot', elapsed_seconds=1, **data)


def state():
    result = Findings()
    result.update(event('run_started', config={'condition': 'periodic', 'model': 'fixture',
        'provider': 'fixture', 'allowance_seconds': 300, 'trial_cap': 12, 'dollar_cap': 3}))
    return result


def render(state, width=120, height=36, **kwargs):
    output = io.StringIO()
    Console(file=output, width=width, height=height, color_system=None).print(
        dashboard(state, width=width, height=height, logs=True, **kwargs))
    return output.getvalue()


def test_log_buffer_matches_full_readable_log_without_summary_truncation():
    result = state()
    update = event('model_call', role='researcher', status='completed',
                   response={'message': {'content': 'Start. ' + 'Full text. ' * 200 + 'END_MARKER'}})
    result.update(update)
    assert '\n'.join(result.log.lines).endswith(format_event(update, verbose=True))
    assert 'END_MARKER' in '\n'.join(result.log.lines)
    assert 'full text in progress.log' not in '\n'.join(result.log.lines)


def test_log_buffer_is_bounded_and_resets_between_runs():
    from study.live_log import LogBuffer
    log = LogBuffer(max_lines=3, max_chars=50)
    log.append('first\nsecond\nthird\nfourth')
    assert list(log.lines) == ['second', 'third', 'fourth']
    log.append('x' * 100 + 'LAST')
    assert log.characters <= 50 and log.lines[-1].endswith('LAST')
    result = state()
    result.update(event('failure', error='OLD_RUN'))
    result.update(event('run_started', config={'condition': 'periodic', 'model': 'fixture',
        'provider': 'fixture', 'allowance_seconds': 300, 'trial_cap': 12, 'dollar_cap': 3}))
    assert 'OLD_RUN' not in '\n'.join(result.log.lines)


def test_log_wraps_literal_text_and_shows_tail_without_clipping_to_first_lines():
    result = state()
    result.update(event('model_call', role='researcher', status='completed',
        response={'message': {'content': '[red]literal[/red] ' + 'abc ' * 1000 + '\nLATEST_END\x1b[2J'}}))
    for width, height in [(80,24), (120,36), (160,40), (45,16)]:
        output = render(result, width, height)
        assert 'Live log' in output and 'LATEST_END' in output
        assert '\x1b' not in output
        assert len(output.splitlines()) <= height
        assert 'NIGHTAGENT' in output
    result.update(event('failure', error='[red]literal[/red]'))
    assert '[red]literal[/red]' in render(result)
    assert 'LATEST_END' not in render(result, focus=True)


def test_structured_diagnostics_are_in_full_log():
    result = state()
    update = event('experiment_diagnostic', trial_id=2, equivalent_trial_ids=[1],
                   warning='This experiment repeats trial 1.')
    result.update(update)
    assert 'This experiment repeats trial 1.' in '\n'.join(result.log.lines)
