from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf

from finance_vibe.analysis_engine import calculate_composite_vibe
from finance_vibe import config


def _download_weekly(ticker: str) -> pd.DataFrame:
    df = yf.download(
        ticker,
        period=config.PERIOD,
        interval=config.INTERVAL,
        progress=False,
        auto_adjust=True,
    )

    if df is None or df.empty:
        raise ValueError(f"No market data found for ticker '{ticker}'")

    # Flatten MultiIndex columns (newer yfinance versions)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Standardize expected OHLCV column casing
    df.columns = [c.capitalize() for c in df.columns]

    # Drop incomplete weekly candle (avoid partial week)
    if config.INTERVAL == "1wk" and len(df.index) >= 1:
        last_date = df.index[-1]
        # yfinance uses timezone-aware timestamps sometimes; weekday() still works
        if last_date.weekday() != 4:  # Friday
            df = df.iloc[:-1]

    if len(df) < 50:
        raise ValueError(f"Not enough history to score '{ticker}' (need >= 50 rows)")

    return df


def compute_vibe_score(ticker: str) -> dict[str, Any]:
    df = _download_weekly(ticker)
    score, latest = calculate_composite_vibe(df)

    # `latest` is a Pandas Series; normalize into JSON-friendly primitives.
    def _f(x):
        if x is None:
            return None
        if isinstance(x, (float, int)):
            return float(x)
        try:
            return float(x)
        except Exception:
            return str(x)

    payload = {
        "ticker": ticker,
        "asOf": datetime.now(timezone.utc).isoformat(),
        "period": config.PERIOD,
        "interval": config.INTERVAL,
        "score": float(score),
        "signals": {
            "close": _f(latest.get("Close")),
            "sma20": _f(latest.get("SMA20")),
            "sma50": _f(latest.get("SMA50")),
            "macdHist": _f(latest.get("MACD_Hist")),
            "macdHistSignal": _f(latest.get("MACD_Hist_Signal")),
            "rsi": _f(latest.get("RSI")),
            "rsiSignal": _f(latest.get("RSI_Signal")),
            "cci": _f(latest.get("CCI")),
            "cciSignal": _f(latest.get("CCI_Signal")),
        },
    }

    return payload

