"""The "first candle rule" with a fair-value-gap entry, on SPY, and its placebo (lesson 03d §8).

This one has no paper behind it, only a popular retail recipe, so its rules are the recipe's most
common form, fixed here before the first run:

1. Mark the high and low of the first 5-minute candle (09:30-09:35).
2. From 09:35, on 1-minute bars, wait for a **fair value gap** that breaks out of that range: three
   bars where the third's low is above the first's high (bullish) and the middle bar closes above
   the range high - or the mirror image for a bearish setup. Only the first setup of the day, and
   only until 11:00.
3. **Enter on the retest**: a limit order at the gap's near edge (the third bar's low for a long),
   live from the next bar until 11:00.
4. **Stop** beyond the first bar of the gap (its low for a long); **target 3R**; anything open at
   the close is sold there.
5. **Size**: 1% of capital at risk, at most 4x leverage. Costs as the Noise Band: $0.0035 per
   share, $0.001 slippage on the stop and the close, a limit needs to trade through by a cent.

**The placebo.** The question is not "did it make money" but "did the gap matter". The placebo
keeps every day's real geometry - how far below the market the limit sits, how far the stop is -
and moves it to a random minute of the same window with a random direction. If the real rule
does no better than the placebo, the gap is decoration and any profit is the bracket's shape.
"""

from dataclasses import asdict, dataclass, field
from datetime import date

import numpy as np

from liquid_atm_quant.intraday.account import DayOutcome
from liquid_atm_quant.intraday.noise_band import SessionGrid


@dataclass(frozen=True)
class FvgParams:
    opening_minutes: int = 5
    last_minute: int = 90
    """Minute index of 11:00: no setup is accepted, and no entry fills, after it."""
    target_r: float = 3.0
    risk_per_trade: float = 0.01
    max_leverage: float = 4.0
    commission_per_share: float = 0.0035
    slippage_per_share: float = 0.001
    touch_buffer: float = 0.01


@dataclass
class Setup:
    minute: int          # the third bar of the gap; the limit is live from minute + 1
    direction: int
    entry: float
    stop: float


@dataclass
class FvgStats:
    setups: int = 0
    filled: int = 0
    targets: int = 0
    stops: int = 0
    closes: int = 0
    r: list[float] = field(default_factory=list)


def find_setup(g: SessionGrid, t: int, highs: np.ndarray, lows: np.ndarray,
               p: FvgParams) -> Setup | None:
    n = p.opening_minutes
    or_high, or_low = np.nanmax(highs[t, :n]), np.nanmin(lows[t, :n])
    close = g.close[t]
    for i in range(n + 2, min(p.last_minute, int(g.last[t]))):
        h1, l1, l3, h3, c2 = highs[t, i - 2], lows[t, i - 2], lows[t, i], highs[t, i], close[i - 1]
        if l3 > h1 and c2 > or_high:
            return Setup(i, 1, l3, l1)
        if h3 < l1 and c2 < or_low:
            return Setup(i, -1, h3, h1)
    return None


def play(g: SessionGrid, t: int, highs: np.ndarray, lows: np.ndarray, s: Setup,
         capital: float, p: FvgParams, stats: FvgStats) -> float:
    d, entry, stop = s.direction, s.entry, s.stop
    risk = (entry - stop) * d
    if risk <= 0:
        return 0.0
    target = entry + d * p.target_r * risk
    last = int(g.last[t])
    fill_at = None
    for j in range(s.minute + 1, min(p.last_minute, last) + 1):
        o = g.open[t, j]
        if d > 0 and lows[t, j] <= entry - p.touch_buffer:
            fill_at, price = j, min(entry, o)
            break
        if d < 0 and highs[t, j] >= entry + p.touch_buffer:
            fill_at, price = j, max(entry, o)
            break
    if fill_at is None:
        return 0.0
    stats.filled += 1
    shares = int(min(capital * p.risk_per_trade / risk, capital * p.max_leverage / price))
    if shares <= 0:
        return 0.0
    exit_price = None
    for j in range(fill_at, last + 1):
        o, h, low = g.open[t, j], highs[t, j], lows[t, j]
        hit_stop = low <= stop if d > 0 else h >= stop
        hit_target = (h >= target + p.touch_buffer if d > 0 else low <= target - p.touch_buffer)
        if hit_stop:                          # pessimistic: the stop wins any shared bar
            raw = stop if j == fill_at else (min(stop, o) if d > 0 else max(stop, o))
            exit_price = raw - d * p.slippage_per_share
            stats.stops += 1
            break
        if hit_target and j > fill_at:
            exit_price = target
            stats.targets += 1
            break
    if exit_price is None:
        exit_price = g.day_close[t] - d * p.slippage_per_share
        stats.closes += 1
    stats.r.append(d * (exit_price - price) / risk)
    return d * shares * (exit_price - price) - 2 * shares * p.commission_per_share


def bar_extremes(minutes, g: SessionGrid) -> tuple[np.ndarray, np.ndarray]:
    """High/low grids aligned with `g` (the grid itself keeps only open and close)."""
    days = minutes.index.date
    r = np.array([g.index[d] for d in days])
    c = np.asarray(minutes.index.hour * 60 + minutes.index.minute - 570)
    highs = np.full(g.close.shape, np.nan)
    lows = np.full(g.close.shape, np.nan)
    highs[r, c] = minutes["h"].to_numpy()
    lows[r, c] = minutes["l"].to_numpy()
    filled = np.isfinite(g.close)
    highs = np.where(np.isfinite(highs), highs, g.close)
    lows = np.where(np.isfinite(lows), lows, g.close)
    highs[~filled] = np.nan
    lows[~filled] = np.nan
    return highs, lows


class FirstCandleFvg:
    name = "fvg_first_candle"

    def __init__(self, grid: SessionGrid, highs: np.ndarray, lows: np.ndarray,
                 params: FvgParams | None = None) -> None:
        self.grid, self.highs, self.lows = grid, highs, lows
        self.params = params or FvgParams()
        self.stats = FvgStats()
        self.setups: dict[int, Setup] = {}

    def day(self, session: date, capital: float) -> DayOutcome:
        t = self.grid.index.get(session)
        if t is None or capital <= 0:
            return DayOutcome(0.0)
        s = find_setup(self.grid, t, self.highs, self.lows, self.params)
        if s is None:
            return DayOutcome(0.0)
        self.stats.setups += 1
        self.setups[t] = s
        before = self.stats.filled
        pnl = play(self.grid, t, self.highs, self.lows, s, capital, self.params, self.stats)
        return DayOutcome(pnl, self.stats.filled - before)

    def diagnostics(self) -> dict:
        r = np.array(self.stats.r) if self.stats.r else np.array([np.nan])
        return {"setups": self.stats.setups, "filled": self.stats.filled,
                "targets": self.stats.targets, "stops": self.stats.stops,
                "held_to_close": self.stats.closes, "mean_r": float(np.nanmean(r)),
                "hit_rate": float(np.nanmean(r > 0)), "params": asdict(self.params)}


def placebo(strategy: FirstCandleFvg, seeds: int = 200) -> dict:
    """Mean R per filled trade for `seeds` placebo runs (see the module docstring)."""
    g, p = strategy.grid, strategy.params
    means = []
    for seed in range(seeds):
        rng = np.random.default_rng(seed)
        stats = FvgStats()
        for t, real in strategy.setups.items():
            minute = int(rng.integers(p.opening_minutes + 2, p.last_minute - 1))
            d = int(rng.choice([-1, 1]))
            anchor = g.close[t, minute]
            depth = abs(g.close[t, real.minute] - real.entry)
            risk = abs(real.entry - real.stop)
            entry = anchor - d * depth
            fake = Setup(minute, d, entry, entry - d * risk)
            play(g, t, strategy.highs, strategy.lows, fake, 100_000.0, p, stats)
        means.append(float(np.mean(stats.r)) if stats.r else np.nan)
    real = float(np.nanmean(strategy.stats.r)) if strategy.stats.r else np.nan
    arr = np.array(means)
    return {"real_mean_r": real, "placebo_mean_r_median": float(np.nanmedian(arr)),
            "placebo_p05": float(np.nanpercentile(arr, 5)),
            "placebo_p95": float(np.nanpercentile(arr, 95)),
            "share_of_placebos_beating_real": float(np.nanmean(arr >= real)), "seeds": seeds}


__all__ = ["FirstCandleFvg", "FvgParams", "Setup", "bar_extremes", "find_setup", "placebo",
           "play"]
