"""Command-local training thread budget; independent API waits reserve no cores."""
import asyncio
from contextlib import asynccontextmanager, AsyncExitStack
import os
import time


def validate_cores(value):
    if type(value) is not int or value < 1:
        raise ValueError('max_cores must be a positive integer')
    return value


def worker_threads(model, cores):
    validate_cores(cores)
    return {'jobs': cores if model == 'random_forest' else 1,
            'openmp': cores if model in ('histogram_gradient_boosting', 'torch_mlp', 'torch_cnn') else 1,
            'blas': cores if model in ('logistic', 'ridge') else 1}


class CorePool:
    def __init__(self, maximum):
        self.limit = min(validate_cores(maximum), os.cpu_count() or 1)
        self.available = self.limit
        self.changed = asyncio.Event()
        self.acquisition_order = asyncio.Lock()

    async def acquire(self):
        # Lock acquisition is FIFO, so a strategy immediately requesting its
        # next fit cannot jump an older waiter woken by release(). Cancellation
        # also removes a waiting request without reserving any CPU capacity.
        async with self.acquisition_order:
            while self.available == 0:
                await self.changed.wait()
                self.changed.clear()
            # Small tabular pilots rarely benefit from very large native thread teams.
            allocated = min(4, self.available)
            self.available -= allocated
            return allocated

    def release(self, cores):
        self.available += cores
        self.changed.set()

    @asynccontextmanager
    async def lease(self, timeout=None):
        # End the queue deadline before yielding: a second cancellation during
        # subprocess cleanup could release the lease while its worker is alive.
        async with asyncio.timeout(timeout):
            cores = await self.acquire()
        try:
            yield cores
        finally:
            self.release(cores)


class BalancedTrials:
    def __init__(self, pool, runner=None, device='cpu'):
        if runner is None:
            from .science import run_trial
            runner = run_trial
        self.pool = pool
        self.runner = runner
        self.device = device
        self.gpu_lock = asyncio.Lock()

    async def __call__(self, *args, timeout, resource_callback=None, **kwargs):
        started = time.monotonic()
        def status(allocated, waiting=False):
            if resource_callback:
                resource_callback(max_cores=self.pool.limit, active_cores=self.pool.limit-self.pool.available,
                                  allocated_cores=allocated, waiting=waiting)
        status(0, waiting=True)
        try:
            async with AsyncExitStack() as stack:
                config = args[2] if len(args) > 2 else kwargs.get('config', {})
                neural = config.get('model', '').startswith('torch_')
                # GPU waiters reserve no CPU threads. Release only after worker cleanup.
                if neural and self.device != 'cpu':
                    async with asyncio.timeout(max(0, timeout-(time.monotonic()-started))):
                        await stack.enter_async_context(self.gpu_lock)
                cores = await stack.enter_async_context(self.pool.lease(timeout=max(0, timeout-(time.monotonic()-started))))
                queued = time.monotonic() - started
                status(cores)
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError('Trial allowance exhausted while waiting for cores')
                if neural:
                    kwargs['device'] = self.device
                result = await self.runner(*args, timeout=remaining, cores=cores, **kwargs)
                return result | {'allocated_cores': cores, 'queue_seconds': queued}
        finally:
            status(0)
