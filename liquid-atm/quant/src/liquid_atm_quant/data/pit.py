"""Point-in-time guard: the truncation test for look-ahead bias (lesson 01 §7).

For a signal f and date t:  f(data[:t])[t] must equal f(data)[t].
If appending FUTURE rows changes the value at t, the signal is reading the future.
"""

from collections.abc import Callable

import numpy as np
import pandas as pd

Signal = Callable[[pd.DataFrame], pd.Series | pd.DataFrame]


class LookAheadError(AssertionError):
    """A signal's value at some date depends on data after that date."""


def _same(a: object, b: object, rtol: float) -> bool:
    x = np.atleast_1d(np.asarray(a, dtype=float))
    y = np.atleast_1d(np.asarray(b, dtype=float))
    return x.shape == y.shape and bool(np.allclose(x, y, rtol=rtol, atol=0.0, equal_nan=True))


def assert_no_lookahead(signal: Signal, data: pd.DataFrame, checks: int = 25,
                        min_history: int = 30, rtol: float = 1e-9, seed: int = 0) -> None:
    """Recompute `signal` on truncated histories at sampled dates and compare with the full run.

    `data` must be sorted by its index (one row per date). Raises LookAheadError on mismatch.
    """
    if not data.index.is_monotonic_increasing:
        raise ValueError("data must be sorted by date")
    n = len(data)
    if n < min_history + 2:
        raise ValueError(f"need at least {min_history + 2} rows")

    full = signal(data)
    rng = np.random.default_rng(seed)
    # Exclude the final row: truncating there changes nothing, so it can never detect a leak.
    positions = sorted(rng.choice(np.arange(min_history, n - 1), size=min(checks, n - 1 - min_history),
                                  replace=False))
    for p in positions:
        t = data.index[p]
        partial = signal(data.iloc[:p + 1])
        if not _same(partial.loc[t], full.loc[t], rtol):
            raise LookAheadError(
                f"value at {t} changes when future rows are appended: "
                f"truncated={partial.loc[t]!r} full={full.loc[t]!r}")
