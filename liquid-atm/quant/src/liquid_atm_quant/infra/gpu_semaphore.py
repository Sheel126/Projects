"""Redis-backed counting semaphore that caps concurrent local-LLM calls (VRAM protection)."""

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files

import redis

_SCRIPT = files("liquid_atm_quant.infra").joinpath("semaphore.lua").read_text()


class SemaphoreTimeout(RuntimeError):
    """Raised when no slot frees up before the deadline."""


class GpuSemaphore:
    def __init__(
        self,
        client: redis.Redis,
        limit: int,
        name: str = "gpu",
        lease_ms: int = 10 * 60_000,
        poll_s: float = 0.25,
    ) -> None:
        self._client = client
        self._key = f"semaphore:{name}"
        self._limit = limit
        self._lease_ms = lease_ms
        self._poll_s = poll_s
        self._script = client.register_script(_SCRIPT)

    def try_acquire(self) -> str | None:
        token = uuid.uuid4().hex
        ok = self._script(keys=[self._key], args=[self._limit, self._lease_ms, token])
        return token if int(ok) == 1 else None

    def release(self, token: str) -> None:
        self._client.zrem(self._key, token)

    @contextmanager
    def slot(self, timeout_s: float = 600.0) -> Iterator[None]:
        deadline = time.monotonic() + timeout_s
        token = self.try_acquire()
        while token is None:
            if time.monotonic() >= deadline:
                raise SemaphoreTimeout(f"{self._key}: no free slot within {timeout_s}s")
            time.sleep(self._poll_s)
            token = self.try_acquire()
        try:
            yield
        finally:
            self.release(token)
