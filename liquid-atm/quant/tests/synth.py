"""Synthetic price paths for the Phase 3 strategy tests.

Each path is deterministic (a fixed zigzag instead of random noise), so every test can say in
advance which filter a name must fail and why. A "breakout" path is the one shape the funnel is
built to find: a long steady rise, a flat month of consolidation, then one close above the range
on heavy volume.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from liquid_atm_quant.backtest.panel import Panel

N = 300            # enough for the 252-session history requirement plus a margin
CONSOLIDATION = 30


def sessions(n: int = N) -> list[date]:
    out, day = [], date(2020, 1, 2)
    while len(out) < n:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def zigzag(n: int, amplitude: float) -> np.ndarray:
    return np.where(np.arange(n) % 2 == 0, 1 + amplitude, 1 - amplitude)


def trend(n: int, start: float = 50.0, daily: float = 0.004, wiggle: float = 0.003) -> np.ndarray:
    return start * (1 + daily) ** np.arange(n) * zigzag(n, wiggle)


def breakout(n: int = N, at: int | None = None, jump: float = 0.03, start: float = 50.0,
             daily: float = 0.004, after: float = 0.002) -> np.ndarray:
    """Rise, a flat `CONSOLIDATION`, a `jump` close at session `at`, then a gentle drift up."""
    at = n - 1 if at is None else at
    flat_from = at - CONSOLIDATION
    closes = np.empty(n)
    closes[:flat_from] = trend(flat_from, start, daily)
    level = closes[flat_from - 1]
    closes[flat_from:at] = level * zigzag(at - flat_from, 0.005)
    closes[at:] = level * (1 + jump) * (1 + after) ** np.arange(n - at)
    return closes


def bars(closes: np.ndarray, range_pct: float = 0.01, volume: float = 1_000_000,
         spikes: dict[int, float] | None = None) -> list[tuple]:
    """(open, high, low, close, volume): open at the previous close, a symmetric range around the
    body, constant volume except at `spikes` ({session: multiple})."""
    out = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i else c
        hi, lo = max(o, c) * (1 + range_pct), min(o, c) * (1 - range_pct)
        v = volume * (spikes or {}).get(i, 1.0)
        out.append((float(o), float(hi), float(lo), float(c), float(v)))
    return out


def panel(series: dict[str, list[tuple]], members: set[str] | None = None,
          days: list[date] | None = None) -> Panel:
    n = max(len(v) for v in series.values())
    days = days or sessions(n)
    rows = [{"trade_date": days[i], "symbol": symbol, "open": o, "high": h, "low": l, "close": c,
             "volume": v, "adj_factor": 1.0, "segment_id": 0}
            for symbol, path in series.items() for i, (o, h, l, c, v) in enumerate(path)]
    out = Panel.from_frame(pd.DataFrame(rows), days)
    if members is not None:
        out.member = np.tile(np.array([s in members for s in out.symbols]), (n, 1))
    return out


def spy(n: int = N, daily: float = 0.0005) -> list[tuple]:
    """A calm uptrend: trend up, about 10% realised vol."""
    return bars(trend(n, 300.0, daily, 0.003), range_pct=0.003, volume=50_000_000)
