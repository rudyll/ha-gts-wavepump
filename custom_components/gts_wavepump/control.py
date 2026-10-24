"""Task-reentrant, device-wide operation ordering (no Home Assistant dependency)."""
from contextlib import asynccontextmanager
from functools import wraps
import asyncio


class OperationSuperseded(RuntimeError):
    """A newer stop invalidated this unfinished operation."""


class OperationGate:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._owner = None
        self._generation = 0
        self._owner_generation = 0

    @asynccontextmanager
    async def hold(self):
        task = asyncio.current_task()
        if self._owner is task:
            yield
            return
        generation = self._generation
        async with self._lock:
            if generation != self._generation:
                raise OperationSuperseded("superseded by a newer stop")
            self._owner_generation = generation
            self._owner = task
            try:
                yield
            finally:
                self._owner = None

    def request_stop(self):
        self._generation += 1

    def check(self):
        if self._owner_generation != self._generation:
            raise OperationSuperseded("unfinished operation superseded by stop")


def serialized(method):
    @wraps(method)
    async def run(self, *args, **kwargs):
        async with self.operations.hold():
            return await method(self, *args, **kwargs)
    return run
