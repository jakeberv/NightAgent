"""Command-local training thread budget; independent API waits reserve no cores."""
import asyncio
from contextlib import asynccontextmanager
import os
import time


def validate_cores(value):
    if type(value) is not int or value < 1:
        raise ValueError('max_cores must be a positive integer')
    return value


def worker_threads(model, cores):
    validate_cores(cores)
    return {'jobs': cores if model == 'random_forest' else 1,
            'openmp': cores if model == 'histogram_gradient_boosting' else 1,
            'blas': cores if model in ('logistic', 'ridge') else 1}


class CorePool:
    def __init__(self, maximum):
        self.limit = min(validate_cores(maximum), os.cpu_count() or 1)
        self.available = self.limit
        self.changed = asyncio.Event()

    async def acquire(self):
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
    def __init__(self, pool, runner=None):
        if runner is None:
            from .science import run_trial
            runner = run_trial
        self.pool = pool
        self.runner = runner

    async def __call__(self, *args, timeout, resource_callback=None, **kwargs):
        started = time.monotonic()
        def status(allocated, waiting=False):
            if resource_callback:
                resource_callback(max_cores=self.pool.limit, active_cores=self.pool.limit-self.pool.available,
                                  allocated_cores=allocated, waiting=waiting)
        status(0, waiting=True)
        try:
            async with self.pool.lease(timeout=max(0, timeout-(time.monotonic()-started))) as cores:
                queued = time.monotonic() - started
                status(cores)
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError('Trial allowance exhausted while waiting for cores')
                result = await self.runner(*args, timeout=remaining, cores=cores, **kwargs)
                return result | {'allocated_cores': cores, 'queue_seconds': queued}
        finally:
            status(0)
