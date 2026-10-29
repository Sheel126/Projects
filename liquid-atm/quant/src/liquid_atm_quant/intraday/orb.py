"""Opening-range breakout on Stocks in Play (Zarattini, Barbon & Aziz 2024; lesson 03d §5).

The paper's rules, written down before the first run. Changing any field of `OrbParams` is a new
trial.

* **Universe**, each morning: point-in-time Russell 1000 members (the paper used all ~7,000 US
  stocks; see §5 for why ours is narrower) with an opening price above $5, a 14-day average
  volume of at least 1M shares, and a 14-day ATR above $0.50. Volume and ATR use the 14 sessions
  *before* today.
* **Stocks in Play**: relative volume = the first 5-minute bar's volume / the average first-5-
  minute volume of the previous 14 sessions. At least 1.0, then the top 20 by relative volume.
* **Direction** from that first bar: up -> a buy-stop at its high; down -> a sell-stop at its low;
  open == close -> nothing.
* **Stop loss** 10% of the 14-day ATR from the fill. No target: anything still open is sold at
  the close.
* **Size**: lose 1% of capital at the stop, capped so the 20 positions together stay within 4x.
* **Costs**: $0.0035 per share commission (the paper's), plus something the paper leaves out:
  both the entry and the stop are *stop* orders, which fill as market orders in a stock that is
  moving, so each pays the engine's stop slippage (5 bp, at least a cent). The paper assumed
  zero slippage on 1,600% of turnover-heavy returns; a replication that copied that would only
  be measuring the assumption.

Fills are read from 1-minute bars with the Phase 2 pessimism: a stop is touched when the bar's
range reaches it, a gap fills at the open, and when the entry bar also reaches the stop, the stop
is assumed to have come second and to have filled - the worse case.
"""

import gzip
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from pathlib import Path

import numpy as np
import pandas as pd

from liquid_atm_quant.intraday.account import DayOutcome
from liquid_atm_quant.intraday.bars import CACHE, NY, rows_to_frame

log = logging.getLogger("intraday.orb")

OPENING = CACHE / "_opening5"
DAYS = CACHE / "_orb_days"
FIELDS = ["o", "h", "l", "c", "v"]
SYMBOLS_PER_OPENING_REQUEST = 400


@dataclass(frozen=True)
class OrbParams:
    min_price: float = 5.0
    min_avg_volume: float = 1_000_000
    min_atr: float = 0.50
    lookback: int = 14
    min_relative_volume: float = 1.0
    top_n: int = 20
    stop_atr: float = 0.10
    risk_per_trade: float = 0.01
    max_leverage: float = 4.0
    commission_per_share: float = 0.0035
    stop_slippage_bps: float = 5.0
    universe: str = "russell1000"

    def as_dict(self) -> dict:
        return asdict(self)


# ---- data ---------------------------------------------------------------------------------

def fetch_opening_bars(client, sessions: list[date], members: dict[date, list[str]],
                       root: Path = OPENING, newest_first: bool = False) -> None:
    """The 09:30 five-minute bar for every index member, cached one gzipped CSV per year.
    `newest_first` lets a second process work from the other end."""
    root.mkdir(parents=True, exist_ok=True)
    for year in sorted({d.year for d in sessions}, reverse=newest_first):
        path = root / f"{year}.csv.gz"
        if path.exists():
            continue
        def one_day(day: date) -> list[tuple]:
            symbols = members.get(day, [])
            start = datetime.combine(day, time(9, 30), NY)
            end = datetime.combine(day, time(9, 31), NY)
            out = []
            for i in range(0, len(symbols), SYMBOLS_PER_OPENING_REQUEST):
                chunk = symbols[i:i + SYMBOLS_PER_OPENING_REQUEST]
                got = client.intraday_bars(chunk, start, end, timeframe="5Min")
                for symbol, bars in got.items():
                    for bar in bars:
                        stamp = pd.Timestamp(bar["t"]).tz_convert(NY)
                        if stamp.time() == time(9, 30):
                            out.append((day, symbol, *(bar[k] for k in FIELDS)))
            return out

        # Each request takes ~2 s to come back; the Redis limiter still holds the account to
        # 190 a minute, so a few threads only fill the wait, never exceed the limit.
        days = [d for d in sessions if d.year == year]
        with ThreadPoolExecutor(max_workers=6) as pool:
            rows = [row for part in pool.map(one_day, days) for row in part]
        log.info("opening bars %d: %d rows over %d sessions", year, len(rows), len(days))
        frame = pd.DataFrame(rows, columns=["day", "symbol", *FIELDS])
        with gzip.open(path, "wt", newline="") as fh:
            frame.to_csv(fh, index=False)


def load_opening_bars(root: Path = OPENING) -> pd.DataFrame:
    frames = [pd.read_csv(p, parse_dates=["day"]) for p in sorted(root.glob("*.csv.gz"))]
    out = pd.concat(frames)
    out["day"] = out["day"].dt.date
    return out


def fetch_day_minutes(client, day: date, symbols: list[str], root: Path = DAYS) -> Path:
    """1-minute bars for one session's Stocks in Play, cached one file per day."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{day.isoformat()}.csv.gz"
    if path.exists() or not symbols:
        return path
    start = datetime.combine(day, time(9, 30), NY)
    end = datetime.combine(day, time(16, 0), NY)
    got = client.intraday_bars(symbols, start, end)
    frames = []
    for symbol, rows in got.items():
        frame = rows_to_frame(rows)
        frame["symbol"] = symbol
        frames.append(frame)
    out = pd.concat(frames) if frames else pd.DataFrame(columns=["symbol"])
    with gzip.open(path, "wt", newline="") as fh:
        out.to_csv(fh, index_label="t")
    return path


def load_day_minutes(day: date, root: Path = DAYS) -> dict[str, pd.DataFrame]:
    path = root / f"{day.isoformat()}.csv.gz"
    if not path.exists():
        return {}
    frame = pd.read_csv(path, index_col="t")
    if frame.empty:
        return {}
    frame.index = pd.to_datetime(frame.index, utc=True).tz_convert(NY)
    return {s: part.drop(columns="symbol") for s, part in frame.groupby("symbol")}


# ---- selection ----------------------------------------------------------------------------

@dataclass
class Candidate:
    symbol: str
    direction: int
    level: float
    """Buy-stop (long) or sell-stop (short) price: the opening bar's high or low."""
    atr: float
    relative_volume: float


def daily_filters(panel, t: int, symbol: str, lookback: int) -> tuple[float, float] | None:
    """(14-day average volume, 14-day ATR), both from sessions before `t`. Raw prices: an
    intraday stop distance is measured in today's dollars."""
    j = panel.index.get(symbol)
    if j is None or t <= lookback:
        return None
    a = panel.arrays
    hi, lo = a["high"][t - lookback:t, j], a["low"][t - lookback:t, j]
    prev = a["close"][t - lookback - 1:t - 1, j]
    vol = a["volume"][t - lookback:t, j]
    if not (np.isfinite(hi).all() and np.isfinite(prev).all()):
        return None
    true_range = np.maximum(hi - lo, np.maximum(np.abs(hi - prev), np.abs(lo - prev)))
    return float(np.mean(vol)), float(np.mean(true_range))


def select(opening: pd.DataFrame, panel, params: OrbParams) -> dict[date, list[Candidate]]:
    """Each session's Stocks in Play, from data known by 09:35 that day."""
    p = params
    out: dict[date, list[Candidate]] = {}
    by_symbol = {s: g.set_index("day").sort_index() for s, g in opening.groupby("symbol")}
    or_volume_avg: dict[tuple[date, str], float] = {}
    for symbol, g in by_symbol.items():
        prior = g["v"].shift(1).rolling(p.lookback, min_periods=p.lookback).mean()
        for day, value in prior.items():
            if np.isfinite(value) and value > 0:
                or_volume_avg[(day, symbol)] = float(value)

    for day, g in opening.groupby("day"):
        t = panel.session_index.get(day)
        if t is None:
            continue
        rows = []
        for r in g.itertuples(index=False):
            base = or_volume_avg.get((day, r.symbol))
            if base is None or r.o <= p.min_price or r.c == r.o:
                continue
            stats = daily_filters(panel, t, r.symbol, p.lookback)
            if stats is None:
                continue
            avg_volume, atr = stats
            if avg_volume < p.min_avg_volume or atr <= p.min_atr:
                continue
            rel = r.v / base
            if rel < p.min_relative_volume:
                continue
            up = r.c > r.o
            rows.append(Candidate(r.symbol, 1 if up else -1, r.h if up else r.l, atr, rel))
        rows.sort(key=lambda c: c.relative_volume, reverse=True)
        out[day] = rows[:p.top_n]
    return out


# ---- the day ------------------------------------------------------------------------------

@dataclass
class OrbStats:
    triggered: int = 0
    stopped: int = 0
    closed: int = 0
    ambiguous: int = 0
    no_data: int = 0
    candidates: int = 0
    r_multiples: list[float] = field(default_factory=list)


def _slip(price: float, bps: float) -> float:
    return max(0.01, price * bps / 10_000)


def trade_one(bars: pd.DataFrame, c: Candidate, shares: int, params: OrbParams,
              stats: OrbStats) -> float:
    """P&L of one candidate over its session's minute bars (from 09:35 on)."""
    after = bars[bars.index.time >= time(9, 35)]
    if after.empty:
        return 0.0
    o, h, low, cl = (after[k].to_numpy() for k in ("o", "h", "l", "c"))
    d, level = c.direction, c.level
    hit = np.flatnonzero(h >= level) if d > 0 else np.flatnonzero(low <= level)
    if hit.size == 0:
        return 0.0
    k = int(hit[0])
    stats.triggered += 1
    raw = max(level, o[k]) if d > 0 else min(level, o[k])
    entry = raw + d * _slip(raw, params.stop_slippage_bps)
    stop = entry - d * params.stop_atr * c.atr
    fees = shares * params.commission_per_share * 2
    risk = params.stop_atr * c.atr

    stopped_at = None
    for i in range(k, len(o)):
        reached = low[i] <= stop if d > 0 else h[i] >= stop
        if reached:
            raw_exit = stop if i == k else (min(stop, o[i]) if d > 0 else max(stop, o[i]))
            stopped_at = raw_exit - d * _slip(raw_exit, params.stop_slippage_bps)
            stats.ambiguous += i == k
            break
    if stopped_at is not None:
        stats.stopped += 1
        exit_price = stopped_at
    else:
        stats.closed += 1
        exit_price = cl[-1]
    stats.r_multiples.append(d * (exit_price - entry) / risk)
    return d * shares * (exit_price - entry) - fees


class OrbInPlay:
    name = "orb_in_play"

    def __init__(self, candidates: dict[date, list[Candidate]], params: OrbParams | None = None,
                 loader=load_day_minutes) -> None:
        self.candidates = candidates
        self.params = params or OrbParams()
        self.loader = loader
        self.stats = OrbStats()

    def day(self, session: date, capital: float) -> DayOutcome:
        p = self.params
        picks = self.candidates.get(session, [])
        if not picks or capital <= 0:
            return DayOutcome(0.0)
        minutes = self.loader(session)
        cap_each = capital * p.max_leverage / p.top_n
        pnl, trades = 0.0, 0
        for c in picks:
            self.stats.candidates += 1
            bars = minutes.get(c.symbol)
            if bars is None or bars.empty:
                self.stats.no_data += 1
                continue
            risk_shares = capital * p.risk_per_trade / (p.stop_atr * c.atr)
            shares = int(min(risk_shares, cap_each / c.level))
            if shares <= 0:
                continue
            before = self.stats.triggered
            pnl += trade_one(bars, c, shares, p, self.stats)
            trades += self.stats.triggered - before
        return DayOutcome(pnl, trades)

    def diagnostics(self) -> dict:
        s = self.stats
        r = np.array(s.r_multiples) if s.r_multiples else np.array([np.nan])
        return {"candidates": s.candidates, "triggered": s.triggered, "stopped": s.stopped,
                "held_to_close": s.closed, "ambiguous_entry_bar": s.ambiguous,
                "missing_minutes": s.no_data, "mean_r_gross": float(np.nanmean(r)),
                "hit_rate": float(np.nanmean(r > 0))}


__all__ = ["Candidate", "OrbInPlay", "OrbParams", "fetch_day_minutes", "fetch_opening_bars",
           "load_day_minutes", "load_opening_bars", "select", "trade_one"]
