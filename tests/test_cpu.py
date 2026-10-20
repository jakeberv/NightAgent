import io

from rich.console import Console

from study.findings import Findings


def test_cpu_sampler_uses_interval_measurements_and_throttles_reads(monkeypatch):
    import study.cpu as cpu
    now = [0.0]
    readings = iter([99.0, 25.0, 0.0])
    monkeypatch.setattr(cpu.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(cpu.psutil, 'cpu_percent', lambda interval: next(readings))
    sampler = cpu.HostCPU()
    assert sampler.sample()['percent'] is None  # First psutil reading is not an interval.
    now[0] = .5
    assert sampler.sample()['percent'] is None
    now[0] = 1
    assert sampler.sample()['percent'] == 25
    now[0] = 1.5
    assert sampler.sample()['history'] == [25]
    now[0] = 2
    assert sampler.sample()['percent'] == 0  # Measured idle is valid, not unknown.
    assert sampler.sample()['history'] == [25, 0]


def test_cpu_sampling_failure_clears_stale_reading_and_reprimes(monkeypatch):
    import study.cpu as cpu
    now = [0.0]
    readings = iter([0, 40, OSError('unavailable'), 88, 20])
    def read(interval):
        value = next(readings)
        if isinstance(value, Exception):
            raise value
        return value
    monkeypatch.setattr(cpu.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(cpu.psutil, 'cpu_percent', read)
    sampler = cpu.HostCPU()
    sampler.sample()
    now[0] = 1
    assert sampler.sample()['percent'] == 40
    now[0] = 2
    assert sampler.sample()['percent'] is None
    assert sampler.sample()['status'] == 'unavailable'
    now[0] = 3
    assert sampler.sample()['percent'] is None
    now[0] = 4
    assert sampler.sample()['percent'] == 20


def test_cpu_history_is_bounded(monkeypatch):
    import study.cpu as cpu
    now = [0.0]
    monkeypatch.setattr(cpu.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(cpu.psutil, 'cpu_percent', lambda interval: 50.0)
    sampler = cpu.HostCPU()
    sampler.sample()
    for i in range(1, 61):
        now[0] = i
        sampler.sample()
    assert sampler.sample()['history'] == [50.0] * 30


def test_dashboard_separates_measured_cpu_from_allocated_slots():
    from study.terminal import dashboard
    state = Findings()
    state.update({'type': 'run_started', 'run_id': 'cpu-test', 'config': {'max_cores': 4}})
    state.update({'type': 'resources', 'run_id': 'cpu-test', 'max_cores': 4,
                  'active_cores': 4, 'allocated_cores': 4, 'waiting': False})
    state.cpu = {'percent': 25.0, 'status': 'measured', 'history': [0, 25, 50]}
    for width, height in [(120, 30), (40, 12)]:
        stream = io.StringIO()
        Console(file=stream, width=width, height=height, color_system=None).print(
            dashboard(state, width=width, height=height))
        output = stream.getvalue()
        assert '25%' in output and 'Host CPU' in output
        assert '4/4 allocated' in output
        assert '▁▃▅' in output


def test_default_single_thread_allocation_returns_to_idle():
    state = Findings()
    state.update({'type': 'run_started', 'run_id': 'serial', 'config': {}})
    state.update({'type': 'trial_started', 'run_id': 'serial', 'trial_id': 1})
    assert state.resources['active_cores'] == 1
    state.update({'type': 'trial_finished', 'run_id': 'serial', 'result': {
        'trial_id': 1, 'status': 'timeout'}})
    assert state.resources['active_cores'] == 0


def test_dashboard_cpu_changes_without_new_experiment_events(monkeypatch):
    import study.cpu as cpu
    from study.terminal import StatusLine
    monkeypatch.setenv('TERM', 'xterm-256color')
    now = [0.0]
    readings = iter([0, 25, 75])
    monkeypatch.setattr(cpu.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(cpu.psutil, 'cpu_percent', lambda interval: next(readings))
    class Terminal(io.StringIO):
        def isatty(self):
            return True
    stream = Terminal()
    display = StatusLine(stream)
    display.console.size = (100, 30)
    state = Findings()
    state.update({'type': 'run_started', 'run_id': 'cpu-live', 'config': {}})
    try:
        display.draw(state, detailed=True)
        for second, percent in [(1, '25%'), (2, '75%')]:
            now[0] = second
            offset = len(stream.getvalue())
            display.draw(state, detailed=True)
            assert percent in stream.getvalue()[offset:]
            assert '\x1b[2K' not in stream.getvalue()[offset:]  # Keep flicker fix.
    finally:
        display.clear()


def test_missing_cpu_dependency_does_not_break_display(monkeypatch):
    import study.cpu as cpu
    monkeypatch.setattr(cpu, 'psutil', None)
    result = cpu.HostCPU().sample()
    assert result['percent'] is None
    assert result['status'] == 'unavailable'


def test_narrow_cpu_history_keeps_the_newest_samples():
    from study.terminal import CPUHistory
    state = Findings()
    state.cpu = {'history': [0, 0, 0, 25, 50, 100]}
    stream = io.StringIO()
    Console(file=stream, width=3, color_system=None).print(CPUHistory(state))
    assert stream.getvalue().strip() == '▃▅█'
