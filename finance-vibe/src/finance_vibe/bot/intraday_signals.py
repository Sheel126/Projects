"""Intraday signal helpers — VWAP, IBS, opening range (research-backed)."""
from __future__ import annotations

from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from finance_vibe.bot import config

ET = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)


def compute_vwap(bars: pd.DataFrame) -> float | None:
    """Volume-weighted average price from 1-min OHLCV bars."""
    if bars is None or bars.empty or "Volume" not in bars.columns:
        return None
    vol = bars["Volume"].astype(float)
    if vol.sum() <= 0:
        return None
    typical = (bars["Open"] + bars["High"] + bars["Low"] + bars["Close"]) / 4.0
    return round(float((typical * vol).sum() / vol.sum()), 4)


def compute_ibs(price: float, day_high: float, day_low: float) -> float | None:
    """Internal Bar Strength: where price sits in today's range (0=low, 1=high)."""
    if day_high <= day_low or price <= 0:
        return None
    return round((price - day_low) / (day_high - day_low), 4)


def compute_opening_range(
    bars: pd.DataFrame, orb_minutes: int | None = None,
) -> dict[str, float | None]:
    """High/low of first N minutes after 9:30 ET."""
    minutes = orb_minutes or config.ORB_MINUTES
    if bars is None or bars.empty:
        return {"or_high": None, "or_low": None, "or_mid": None}

    df = bars.copy()
    if "Timestamp" in df.columns:
        ts = pd.to_datetime(df["Timestamp"], utc=True).dt.tz_convert(ET)
    elif "Date" in df.columns:
        ts = pd.to_datetime(df["Date"], utc=True).dt.tz_convert(ET)
    else:
        return {"or_high": None, "or_low": None, "or_mid": None}

    df["_ts"] = ts
    today = datetime.now(ET).date()
    open_dt = datetime.combine(today, MARKET_OPEN, tzinfo=ET)
    end_dt = open_dt + pd.Timedelta(minutes=minutes)

    window = df[(df["_ts"] >= open_dt) & (df["_ts"] < end_dt)]
    if window.empty:
        # Fallback: use first N bars of session
        session = df[df["_ts"].dt.date == today]
        window = session.head(minutes) if len(session) >= 1 else session

    if window.empty:
        return {"or_high": None, "or_low": None, "or_mid": None}

    hi = float(window["High"].max())
    lo = float(window["Low"].min())
    return {"or_high": hi, "or_low": lo, "or_mid": round((hi + lo) / 2, 4)}


def orb_signal(price: float, or_high: float | None, or_low: float | None) -> str | None:
    """Opening range breakout direction."""
    if or_high is None or or_low is None or price <= 0:
        return None
    if price > or_high:
        return "ORB_BREAKOUT_UP"
    if price < or_low:
        return "ORB_BREAKOUT_DOWN"
    return "ORB_INSIDE"


def enrich_intraday_metrics(
    price: float,
    bars: pd.DataFrame | None,
) -> dict[str, Any]:
    """Attach VWAP, IBS, ORB from intraday bars."""
    out: dict[str, Any] = {
        "vwap": None,
        "price_vs_vwap_pct": None,
        "ibs": None,
        "day_high": None,
        "day_low": None,
        "or_high": None,
        "or_low": None,
        "orb_signal": None,
    }
    if bars is None or bars.empty or price <= 0:
        return out

    vwap = compute_vwap(bars)
    out["vwap"] = vwap
    if vwap and vwap > 0:
        out["price_vs_vwap_pct"] = round((price - vwap) / vwap * 100, 3)

    today = datetime.now(ET).date()
    ts_col = "Timestamp" if "Timestamp" in bars.columns else "Date"
    ts = pd.to_datetime(bars[ts_col], utc=True).dt.tz_convert(ET)
    session = bars[ts.dt.date == today]
    if session.empty:
        session = bars

    day_high = float(session["High"].max())
    day_low = float(session["Low"].min())
    out["day_high"] = day_high
    out["day_low"] = day_low
    out["ibs"] = compute_ibs(price, day_high, day_low)

    orb = compute_opening_range(bars)
    out["or_high"] = orb["or_high"]
    out["or_low"] = orb["or_low"]
    out["orb_signal"] = orb_signal(price, orb["or_high"], orb["or_low"])
    return out


def intraday_buy_bonus(snap: Any) -> float:
    """Score boost from VWAP/IBS mean-reversion research."""
    bonus = 0.0
    if snap.vwap and snap.price_vs_vwap_pct is not None:
        if snap.price_vs_vwap_pct <= -0.15:
            bonus += min(22.0, abs(snap.price_vs_vwap_pct) * 8)
        elif snap.price_vs_vwap_pct <= -0.05:
            bonus += 8.0
    if snap.ibs is not None:
        if snap.ibs <= 0.2:
            bonus += 20.0
        elif snap.ibs <= 0.35:
            bonus += 12.0
    if snap.orb_signal == "ORB_BREAKOUT_UP":
        bonus += 10.0
    return bonus
