"""Redis sliding-window rate limiter backed by an atomic Lua script."""

import time
import uuid
from dataclasses import dataclass
from importlib.resources import files

import redis

_SCRIPT = files("liquid_atm_quant.infra").joinpath("sliding_window.lua").read_text()


class RateLimitTimeout(RuntimeError):
    """Raised when a blocking acquire could not get a slot before its deadline."""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    in_window: int
    retry_after_ms: int


class SlidingWindowRateLimiter:
    """At most `limit` requests in any rolling `window_ms` for the named resource.

    Every process that shares the Redis instance shares the budget, which is the
    point: two workers hitting EDGAR must not each think they own 10 req/s.
    """

    def __init__(self, client: redis.Redis, name: str, limit: int, window_ms: int) -> None:
        if limit < 1 or window_ms < 1:
            raise ValueError("limit and window_ms must be positive")
        self._key = f"ratelimit:{name}"
        self._limit = limit
        self._window_ms = window_ms
        # A saturated window frees slots only as old requests age out, so the default wait must
        # exceed the window itself; 30s against a 60s window fails while the limiter is healthy.
        self.default_timeout_s = max(30.0, 2 * window_ms / 1000)
        self._script = client.register_script(_SCRIPT)

    def try_acquire(self) -> Decision:
        allowed, in_window, retry_after = self._script(
            keys=[self._key],
            args=[self._window_ms, self._limit, uuid.uuid4().hex],
        )
        return Decision(bool(int(allowed)), int(in_window), int(retry_after))

    def acquire(self, timeout_s: float | None = None) -> None:
        """Block until a slot is free, sleeping exactly as long as the script says."""
        timeout_s = self.default_timeout_s if timeout_s is None else timeout_s
        deadline = time.monotonic() + timeout_s
        while True:
            decision = self.try_acquire()
            if decision.allowed:
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RateLimitTimeout(f"{self._key}: no slot within {timeout_s}s")
            time.sleep(min(decision.retry_after_ms / 1000, remaining))


# Published limits for the free APIs we use, with a little headroom.
def alpaca_limiter(client: redis.Redis) -> SlidingWindowRateLimiter:
    return SlidingWindowRateLimiter(client, "alpaca", limit=190, window_ms=60_000)


def edgar_limiter(client: redis.Redis) -> SlidingWindowRateLimiter:
    return SlidingWindowRateLimiter(client, "edgar", limit=8, window_ms=1_000)


def yfinance_limiter(client: redis.Redis) -> SlidingWindowRateLimiter:
    # Unofficial API with undocumented limits: stay deliberately slow.
    return SlidingWindowRateLimiter(client, "yfinance", limit=30, window_ms=60_000)
