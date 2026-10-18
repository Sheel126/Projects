"""yfinance: ^VIX, pre-2016 ETF history, and cross-checks. Never stock history (no delisted names).

Yahoo's `Close` is split-adjusted (not raw) and `Adj Close` is split+dividend adjusted, so rows
stored from here have close = split-adjusted close and adj_factor = Adj Close / Close.
"""

from collections.abc import Sequence
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from liquid_atm_quant.data.db import Bar
from liquid_atm_quant.infra.rate_limiter import SlidingWindowRateLimiter


def _frame(symbol: str, start: date, end: date) -> pd.DataFrame:
    # yfinance's `end` is exclusive.
    df = yf.download(symbol, start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
                     auto_adjust=False, progress=False, threads=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Close"])


def daily_bars(symbols: Sequence[str], start: date, end: date, limiter: SlidingWindowRateLimiter) -> list[Bar]:
    out: list[Bar] = []
    for symbol in symbols:
        limiter.acquire()
        for ts, r in _frame(symbol, start, end).iterrows():
            close = float(r["Close"])
            out.append(Bar(symbol, ts.date(), float(r["Open"]), float(r["High"]), float(r["Low"]), close,
                           int(r["Volume"]), None, round(float(r["Adj Close"]) / close, 10), "yfinance"))
    return out


def adjusted_closes(symbol: str, start: date, end: date, limiter: SlidingWindowRateLimiter) -> pd.Series:
    """Fully adjusted closes indexed by date, for cross-checking another source."""
    limiter.acquire()
    df = _frame(symbol, start, end)
    return pd.Series(df["Adj Close"].to_numpy(dtype=float), index=[ts.date() for ts in df.index])
