import threading
import time

import pytest

from liquid_atm_quant.infra.gpu_semaphore import GpuSemaphore, SemaphoreTimeout
from liquid_atm_quant.infra.rate_limiter import RateLimitTimeout, SlidingWindowRateLimiter


def test_admits_exactly_limit_then_denies(redis_client):
    limiter = SlidingWindowRateLimiter(redis_client, "t1", limit=5, window_ms=10_000)
    decisions = [limiter.try_acquire() for _ in range(7)]
    assert [d.allowed for d in decisions] == [True] * 5 + [False] * 2
    assert decisions[-1].in_window == 5
    assert 0 < decisions[-1].retry_after_ms <= 10_000


def test_window_slides(redis_client):
    limiter = SlidingWindowRateLimiter(redis_client, "t2", limit=2, window_ms=300)
    assert limiter.try_acquire().allowed
    assert limiter.try_acquire().allowed
    assert not limiter.try_acquire().allowed
    time.sleep(0.35)
    assert limiter.try_acquire().allowed


def test_concurrent_callers_never_exceed_limit(redis_client):
    limiter = SlidingWindowRateLimiter(redis_client, "t3", limit=10, window_ms=60_000)
    admitted: list[bool] = []
    lock = threading.Lock()

    def worker():
        for _ in range(10):
            ok = limiter.try_acquire().allowed
            with lock:
                admitted.append(ok)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(admitted) == 80
    assert sum(admitted) == 10


def test_blocking_acquire_waits_then_times_out(redis_client):
    limiter = SlidingWindowRateLimiter(redis_client, "t4", limit=1, window_ms=200)
    limiter.acquire()
    started = time.monotonic()
    limiter.acquire(timeout_s=2)  # must wait for the window to slide
    assert time.monotonic() - started >= 0.1

    slow = SlidingWindowRateLimiter(redis_client, "t5", limit=1, window_ms=60_000)
    slow.acquire()
    with pytest.raises(RateLimitTimeout):
        slow.acquire(timeout_s=0.2)


def test_invalid_config_rejected(redis_client):
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(redis_client, "bad", limit=0, window_ms=1000)


def test_gpu_semaphore_caps_concurrency_and_releases(redis_client):
    sem = GpuSemaphore(redis_client, limit=1, poll_s=0.01)
    token = sem.try_acquire()
    assert token is not None
    assert sem.try_acquire() is None
    sem.release(token)
    assert sem.try_acquire() is not None


def test_gpu_semaphore_slot_times_out_when_busy(redis_client):
    sem = GpuSemaphore(redis_client, limit=1, poll_s=0.01)
    with sem.slot():
        with pytest.raises(SemaphoreTimeout):
            with sem.slot(timeout_s=0.1):
                pass
    with sem.slot(timeout_s=0.1):  # released after the outer block
        pass


def test_gpu_semaphore_expired_lease_frees_slot(redis_client):
    sem = GpuSemaphore(redis_client, limit=1, lease_ms=100, poll_s=0.01)
    assert sem.try_acquire() is not None  # holder "crashes" and never releases
    time.sleep(0.15)
    assert sem.try_acquire() is not None
