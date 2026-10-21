import asyncio
from datetime import datetime, timedelta, timezone
import json

import pytest

from study.config import StudyConfig


@pytest.mark.parametrize('value', [0, -1, True, 1.5])
def test_invalid_core_ceiling_is_rejected(value):
    with pytest.raises(ValueError, match='max_cores'):
        StudyConfig(max_cores=value)


def test_pool_caps_combined_training_and_returns_cores_after_cancellation(monkeypatch):
    monkeypatch.setattr('study.resources.os.cpu_count', lambda: 8)
    from study.resources import CorePool
    async def scenario():
        pool = CorePool(3)
        async with pool.lease() as first:
            assert first == 3
            waiter = asyncio.create_task(pool.acquire())
            await asyncio.sleep(.01)
            assert not waiter.done()
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter
        assert pool.available == 3
        async with pool.lease() as again:
            assert again == 3
        assert pool.available == pool.limit
    asyncio.run(scenario())


def test_pool_gives_queued_waiter_priority_over_immediate_reacquisition():
    from study.resources import CorePool
    async def scenario():
        pool = CorePool(2)
        order = []
        async def waiting_fit():
            async with pool.lease():
                order.append('queued')
        async with pool.lease():
            waiter = asyncio.create_task(waiting_fit())
            await asyncio.sleep(0)
            assert not waiter.done()
        # A scripted strategy can request its next fit without an intervening
        # event-loop turn. It must not starve the other strategy already queued.
        async with pool.lease():
            order.append('newcomer')
        await waiter
        assert order == ['queued', 'newcomer']
        assert pool.available == pool.limit
    asyncio.run(asyncio.wait_for(scenario(), timeout=2))


def test_cancelled_first_core_waiter_does_not_block_the_next_waiter():
    from study.resources import CorePool
    async def scenario():
        pool = CorePool(2)
        order = []
        async def waiting_fit(name):
            async with pool.lease():
                order.append(name)
        async with pool.lease():
            cancelled = asyncio.create_task(waiting_fit('cancelled'))
            survivor = asyncio.create_task(waiting_fit('survivor'))
            await asyncio.sleep(0)
            cancelled.cancel()
            with pytest.raises(asyncio.CancelledError):
                await cancelled
        async with pool.lease():
            order.append('newcomer')
        await survivor
        assert order == ['survivor', 'newcomer']
        assert pool.available == pool.limit
    asyncio.run(asyncio.wait_for(scenario(), timeout=2))


def test_parallel_suite_overlaps_runs_and_preserves_schedule_order(tmp_path):
    from study.suite import run_suite
    active = peak = 0
    seen = []
    async def runner(config, data, directory, model, **kwargs):
        nonlocal active, peak
        assert 'trial_runner' in kwargs
        active += 1
        peak = max(peak, active)
        seen.append(config.condition)
        await asyncio.sleep(.02)
        active -= 1
        return {'condition': config.condition, 'stop_reason': 'trial_cap'}
    output = tmp_path / 'suite'
    result = asyncio.run(run_suite(StudyConfig(max_cores=4, allowance_seconds=1), tmp_path, output,
        repeats=1, deadline=datetime.now(timezone.utc)+timedelta(seconds=30), reserve_seconds=5,
        model_factory=lambda _: None, runner=runner))
    manifest = json.loads((output / 'suite.json').read_text())
    assert peak == 2
    assert [r['condition'] for r in result] == [r['condition'] for r in manifest['schedule']]
    assert manifest['execution']['max_cores'] <= 4
    assert manifest['execution']['concurrent_runs'] == 2


def test_worker_uses_allocation_without_nested_thread_explosion():
    from study.resources import worker_threads
    assert worker_threads('random_forest', 4) == {'jobs': 4, 'openmp': 1, 'blas': 1}
    assert worker_threads('histogram_gradient_boosting', 4) == {'jobs': 1, 'openmp': 4, 'blas': 1}
    assert worker_threads('logistic', 4) == {'jobs': 1, 'openmp': 1, 'blas': 4}
    assert worker_threads('torch_mlp', 2) == {'jobs': 1, 'openmp': 2, 'blas': 1}
    assert worker_threads('torch_cnn', 3) == {'jobs': 1, 'openmp': 3, 'blas': 1}


def test_shared_balancer_never_exceeds_ceiling_and_records_queue_time(tmp_path):
    from study.resources import CorePool, BalancedTrials
    used = peak = 0
    async def fake(*args, cores, **kwargs):
        nonlocal used, peak
        used += cores
        peak = max(peak, used)
        await asyncio.sleep(.02)
        used -= cores
        return {'status': 'completed'}
    async def scenario():
        pool = CorePool(6)
        run = BalancedTrials(pool, runner=fake)
        results = await asyncio.gather(*(run(tmp_path, tmp_path, {}, seed=42, timeout=2) for _ in range(3)))
        assert peak <= 6 and peak > 1
        assert sum(r['queue_seconds'] > 0 for r in results) == 3
        assert all(1 <= r['allocated_cores'] <= 4 for r in results)
        assert pool.available == pool.limit
    asyncio.run(scenario())


def test_interleaved_run_progress_never_mixes_selected_models():
    import io
    from study.progress import ConsoleProgress
    progress = ConsoleProgress(stream=io.StringIO())
    for run, score in [('first', .91), ('second', .95)]:
        progress({'type': 'run_started', 'run_id': run, 'config': {}})
        progress({'type': 'selection', 'run_id': run, 'best': {'trial_id': 1, 'score': score}})
    progress({'type': 'model_call_started', 'run_id': 'first', 'role': 'researcher'})
    assert progress.findings.run_id == 'first'
    assert progress.findings.best['score'] == .91


def test_real_worker_respects_core_allocation_and_keeps_secrets_out(tmp_path):
    import joblib
    from study.science import prepare_dataset, run_trial, _worker_env
    data = tmp_path / 'data'
    prepare_dataset(data, synthetic=True)
    config = {'model': 'random_forest', 'preprocessing': 'none', 'params': {'n_estimators': 10}}
    result = asyncio.run(run_trial(data, tmp_path / 'trial', config, seed=42, timeout=20, cores=2))
    assert result['status'] == 'completed'
    artifact = joblib.load(result['artifact'])
    assert artifact['pipeline'].steps[-1][1].n_jobs == 2
    assert artifact['metadata']['allocated_cores'] == 2
    env = _worker_env(42, 2, 'random_forest')
    assert env['OMP_NUM_THREADS'] == env['OPENBLAS_NUM_THREADS'] == '1'
    assert env['LOKY_MAX_CPU_COUNT'] == '2'
    assert not any('KEY' in name or 'TOKEN' in name for name in env)


def test_balancer_cancellation_and_timeout_release_the_entire_budget(tmp_path):
    from study.resources import CorePool, BalancedTrials
    async def scenario():
        pool = CorePool(2)
        entered = asyncio.Event()
        async def stalled(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()
        run = BalancedTrials(pool, runner=stalled)
        active = asyncio.create_task(run(tmp_path, timeout=10))
        await entered.wait()
        with pytest.raises(TimeoutError):
            await run(tmp_path, timeout=.01)
        assert pool.available == 0
        active.cancel()
        with pytest.raises(asyncio.CancelledError):
            await active
        assert pool.available == pool.limit
    asyncio.run(scenario())


def test_balancer_waits_for_cleanup_before_releasing_cores():
    import time
    from study.resources import CorePool, BalancedTrials
    async def scenario():
        pool = CorePool(2)
        cleaned = False
        async def runner(**kwargs):
            nonlocal cleaned
            try:
                await asyncio.Event().wait()
            finally:
                assert pool.available == 0
                await asyncio.sleep(.05)
                cleaned = True
        def callback(**status):
            if status['waiting']:
                time.sleep(.005)
        run = BalancedTrials(pool, runner=runner)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(run(timeout=.02, resource_callback=callback), timeout=.02)
        assert cleaned
        assert pool.available == pool.limit
    asyncio.run(scenario())


def test_recovery_and_report_exclude_queue_time(tmp_path):
    from dataclasses import asdict
    from study.recovery import recover_run
    from study.report_loading import trials_from_events
    from study.problem import legacy_problem
    problem = legacy_problem()
    (tmp_path / 'resolved-config.json').write_text(json.dumps({
        'config': asdict(StudyConfig(max_cores=2)), 'problem': problem.to_dict(),
        'problem_hash': problem.fingerprint}))
    results = [
        {'trial_id': 1, 'status': 'timeout', 'duration_seconds': 8,
         'queue_seconds': 5, 'training_seconds': 3, 'elapsed_seconds': 10},
        {'trial_id': 2, 'status': 'timeout', 'duration_seconds': 2,
         'training_seconds': 2, 'elapsed_seconds': 12},
    ]
    events = [{'type': 'trial_finished', 'result': result, 'elapsed_seconds': result['elapsed_seconds']}
              for result in results]
    (tmp_path / 'events.jsonl').write_text(''.join(json.dumps(event) + '\n' for event in events))
    assert recover_run(tmp_path)['training_seconds'] == 5
    assert [trial['training_seconds'] for trial in trials_from_events(events, {})] == [3, 2]


def test_gpu_queue_serializes_gpu_fits_without_blocking_cpu_fits(tmp_path, monkeypatch):
    monkeypatch.setattr('study.resources.os.cpu_count', lambda: 8)
    from study.resources import CorePool, BalancedTrials
    async def scenario():
        active_gpu = peak_gpu = 0
        gpu_started = asyncio.Event()
        cpu_overlapped = []
        async def runner(data, output, config, **kwargs):
            nonlocal active_gpu, peak_gpu
            if config['model'].startswith('torch_'):
                assert kwargs['device'] == 'mps'
                active_gpu += 1
                peak_gpu = max(peak_gpu, active_gpu)
                gpu_started.set()
                await asyncio.sleep(.03)
                active_gpu -= 1
            else:
                await gpu_started.wait()
                cpu_overlapped.append(active_gpu > 0)
            return {'status': 'completed'}
        pool = CorePool(8)
        balanced = BalancedTrials(pool, runner=runner, device='mps')
        jobs = [balanced(tmp_path, tmp_path, {'model': m}, seed=42, timeout=2)
                for m in ('torch_mlp', 'torch_cnn', 'logistic')]
        await asyncio.gather(*jobs)
        assert peak_gpu == 1 and cpu_overlapped == [True]
        assert pool.available == pool.limit
    asyncio.run(scenario())


@pytest.mark.parametrize('exit_mode', ['cancellation', 'timeout'])
def test_gpu_waiter_exit_never_releases_active_lock_or_reserves_cores(exit_mode, monkeypatch):
    from study.resources import CorePool, BalancedTrials
    monkeypatch.setattr('study.resources.os.cpu_count', lambda: 8)
    async def scenario():
        pool = CorePool(8)
        entered = asyncio.Event()
        release_worker = asyncio.Event()
        fits = 0
        async def runner(**kwargs):
            nonlocal fits
            fits += 1
            entered.set()
            await release_worker.wait()
            return {'status': 'completed'}
        balanced = BalancedTrials(pool, runner=runner, device='mps')
        active = asyncio.create_task(balanced(config={'model': 'torch_mlp'}, timeout=2))
        await entered.wait()
        waiter = asyncio.create_task(balanced(config={'model': 'torch_cnn'}, timeout=.02 if exit_mode == 'timeout' else 2))
        await asyncio.sleep(0)
        assert pool.available == 4
        if exit_mode == 'cancellation':
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter
        else:
            with pytest.raises(TimeoutError):
                await waiter
        assert fits == 1
        assert balanced.gpu_lock.locked()
        assert pool.available == 4
        release_worker.set()
        await active
        assert not balanced.gpu_lock.locked()
        assert pool.available == pool.limit
        assert (await balanced(config={'model': 'torch_cnn'}, timeout=1))['status'] == 'completed'
    asyncio.run(asyncio.wait_for(scenario(), timeout=5))


@pytest.mark.parametrize('exit_mode', ['cancellation', 'timeout'])
def test_gpu_lock_released_when_its_holder_exits_while_waiting_for_cpu(exit_mode):
    from study.resources import CorePool, BalancedTrials
    async def scenario():
        pool = CorePool(2)
        async def runner(**kwargs):
            return {'status': 'completed'}
        balanced = BalancedTrials(pool, runner=runner, device='mps')
        async with pool.lease():
            waiter = asyncio.create_task(balanced(config={'model': 'torch_mlp'}, timeout=.02 if exit_mode == 'timeout' else 2))
            await asyncio.sleep(0)
            assert balanced.gpu_lock.locked()
            if exit_mode == 'cancellation':
                waiter.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await waiter
            else:
                with pytest.raises(TimeoutError):
                    await waiter
            assert not balanced.gpu_lock.locked()
            assert pool.available == 0
        assert pool.available == pool.limit
        assert (await balanced(config={'model': 'torch_cnn'}, timeout=1))['status'] == 'completed'
    asyncio.run(asyncio.wait_for(scenario(), timeout=5))


@pytest.mark.parametrize('exit_mode', ['cancellation', 'timeout'])
def test_gpu_and_cpu_leases_remain_held_until_cancelled_worker_cleanup_finishes(exit_mode):
    from study.resources import CorePool, BalancedTrials
    async def scenario():
        pool = CorePool(2)
        started = asyncio.Event()
        cleanup_started = asyncio.Event()
        permit_cleanup = asyncio.Event()
        async def runner(**kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleanup_started.set()
                await permit_cleanup.wait()
                assert balanced.gpu_lock.locked()
                assert pool.available == 0
        balanced = BalancedTrials(pool, runner=runner, device='mps')
        trial = balanced(config={'model': 'torch_mlp'}, timeout=2)
        active = asyncio.create_task(asyncio.wait_for(trial, timeout=.02) if exit_mode == 'timeout' else trial)
        await started.wait()
        if exit_mode == 'cancellation':
            active.cancel()
        await cleanup_started.wait()
        assert not active.done()
        assert balanced.gpu_lock.locked()
        assert pool.available == 0
        permit_cleanup.set()
        with pytest.raises(asyncio.CancelledError if exit_mode == 'cancellation' else TimeoutError):
            await active
        assert not balanced.gpu_lock.locked()
        assert pool.available == pool.limit
    asyncio.run(asyncio.wait_for(scenario(), timeout=5))


@pytest.mark.parametrize('available', [1, 2, 4])
def test_pool_respects_small_host_cpu_count(available, monkeypatch):
    from study.resources import CorePool
    monkeypatch.setattr('study.resources.os.cpu_count', lambda: available)
    pool = CorePool(8)
    assert pool.limit == available
    async def scenario():
        async with pool.lease() as cores:
            assert cores == available
            assert pool.available == 0
        assert pool.available == available
    asyncio.run(scenario())
