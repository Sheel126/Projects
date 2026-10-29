"""The Noise Band: intraday momentum on SPY (Zarattini, Aziz & Barbon 2024; lesson 03d §4).

Every rule below is the paper's, written down before the first run. Changing any field of
`NoiseBandParams` is a new trial.

1. **Noise area.** For each minute of the day, sigma = the average over the previous 14 sessions
   of |close at that minute / that day's open - 1|. The bounds are
   `max(open, prior close) * (1 + vm * sigma)` and `min(open, prior close) * (1 - vm * sigma)`:
   an overnight gap widens the side it moved away from.
2. **Decisions only on the half hour**, 10:00 through 15:30, using the close of the minute that
   ends at that time. The order fills at the next minute's open, plus slippage.
3. **Position.** Long while price is above both the upper bound and the session VWAP, short while
   it is below both the lower bound and VWAP, otherwise flat. That one rule is the paper's entry
   (cross the band) and its trailing stop (`max(UB, VWAP)` for longs, `min(LB, VWAP)` for shorts)
   at once, and it cannot exit and re-enter the same side at the same check.
4. **Flat at the close**, every day.
5. **Size**, fixed for the day: `capital * min(4, 2% / sigma_daily) / open` shares, where
   sigma_daily is the 14-session standard deviation of SPY's close-to-close returns.
6. **Costs**: $0.0035 per share commission and $0.001 per share slippage, the paper's numbers.
   Alpaca charges no commission, so this is conservative by about a third of the cost.
"""

from dataclasses import asdict, dataclass
from datetime import date

import numpy as np
import pandas as pd

from liquid_atm_quant.intraday.account import DayOutcome

MINUTES = 390


@dataclass(frozen=True)
class NoiseBandParams:
    lookback: int = 14
    vm: float = 1.0
    """Volatility multiplier on the noise area. The paper reports 1.0 and says ~1.5 looked better
    in hindsight; 1.0 is used because choosing 1.5 would be fitting to the paper's own sample."""
    vol_target: float = 0.02
    vol_lookback: int = 14
    max_leverage: float = 4.0
    first_check: int = 29
    """Minute index (from 09:30) of the bar ending 10:00."""
    check_every: int = 30
    last_check: int = 359
    """The bar ending 15:30. The position is then held to the close."""
    commission_per_share: float = 0.0035
    slippage_per_share: float = 0.001
    min_history: int = 10
    """Sessions of minute-history a minute needs before its sigma is trusted."""

    def as_dict(self) -> dict:
        return asdict(self)


class SessionGrid:
    """Minute bars as session x minute-of-day arrays. Missing minutes are carried forward within
    the session; minutes after an early close stay NaN."""

    def __init__(self, minutes: pd.DataFrame) -> None:
        days = minutes.index.date
        self.sessions: list[date] = sorted(set(days))
        row = {d: i for i, d in enumerate(self.sessions)}
        clock = minutes.index.hour * 60 + minutes.index.minute - (9 * 60 + 30)
        r = np.array([row[d] for d in days])
        c = np.asarray(clock)
        shape = (len(self.sessions), MINUTES)
        self.open = np.full(shape, np.nan)
        self.close = np.full(shape, np.nan)
        self.volume = np.zeros(shape)
        self.vwap_num = np.zeros(shape)
        self.open[r, c] = minutes["o"].to_numpy()
        self.close[r, c] = minutes["c"].to_numpy()
        self.volume[r, c] = minutes["v"].to_numpy()
        self.vwap_num[r, c] = (minutes["vw"] * minutes["v"]).to_numpy()

        # The session's last printed minute: everything after it is past an early close.
        printed = np.isfinite(self.close)
        self.last = np.where(printed.any(axis=1),
                             MINUTES - 1 - np.argmax(printed[:, ::-1], axis=1), -1)
        self.close = pd.DataFrame(self.close.T).ffill().to_numpy().T.copy()
        self.open = np.where(np.isfinite(self.open), self.open, self.close)
        after = np.arange(MINUTES)[None, :] > self.last[:, None]
        self.close[after] = np.nan
        self.open[after] = np.nan

        self.day_open = self.open[:, 0]
        self.day_close = np.array([self.close[i, k] if k >= 0 else np.nan
                                   for i, k in enumerate(self.last)])
        with np.errstate(invalid="ignore", divide="ignore"):
            self.vwap = np.cumsum(self.vwap_num, axis=1) / np.cumsum(self.volume, axis=1)
        self.index = row


class NoiseBand:
    name = "noise_band"

    def __init__(self, grid: SessionGrid, params: NoiseBandParams | None = None) -> None:
        self.grid = grid
        self.params = params or NoiseBandParams()
        p = self.params
        g = grid
        with np.errstate(invalid="ignore", divide="ignore"):
            move = np.abs(g.close / g.day_open[:, None] - 1.0)
        # sigma[t] uses sessions t-14 .. t-1 only.
        self.sigma = np.full_like(move, np.nan)
        for t in range(1, len(g.sessions)):
            window = move[max(0, t - p.lookback):t]
            counts = np.isfinite(window).sum(axis=0)
            with np.errstate(invalid="ignore"):
                mean = np.nanmean(window, axis=0) if len(window) else np.nan
            self.sigma[t] = np.where(counts >= p.min_history, mean, np.nan)
        rets = g.day_close[1:] / g.day_close[:-1] - 1.0
        self.daily_vol = np.full(len(g.sessions), np.nan)
        for t in range(p.vol_lookback + 1, len(g.sessions)):
            self.daily_vol[t] = np.std(rets[t - 1 - p.vol_lookback:t - 1], ddof=1)
        self.checks = list(range(p.first_check, p.last_check + 1, p.check_every))
        self.days_skipped = 0

    def leverage(self, t: int) -> float:
        vol = self.daily_vol[t]
        if not np.isfinite(vol) or vol <= 0:
            return 0.0
        return min(self.params.max_leverage, self.params.vol_target / vol)

    def bounds(self, t: int, k: int) -> tuple[float, float]:
        g, p = self.grid, self.params
        prior_close = g.day_close[t - 1] if t > 0 else g.day_open[t]
        sigma = self.sigma[t, k]
        upper = max(g.day_open[t], prior_close) * (1 + p.vm * sigma)
        lower = min(g.day_open[t], prior_close) * (1 - p.vm * sigma)
        return upper, lower

    def signal(self, t: int, k: int) -> int:
        price, vwap = self.grid.close[t, k], self.grid.vwap[t, k]
        upper, lower = self.bounds(t, k)
        if not (np.isfinite(price) and np.isfinite(upper) and np.isfinite(vwap)):
            return 0
        if price > upper and price > vwap:
            return 1
        if price < lower and price < vwap:
            return -1
        return 0

    def day(self, session: date, capital: float) -> DayOutcome:
        g, p = self.grid, self.params
        t = g.index.get(session)
        if t is None or t == 0 or capital <= 0:
            return DayOutcome(0.0)
        lev = self.leverage(t)
        if lev <= 0 or not np.isfinite(self.sigma[t, p.first_check]):
            self.days_skipped += 1
            return DayOutcome(0.0)
        shares = int(capital * lev / g.day_open[t])
        if shares <= 0:
            return DayOutcome(0.0)

        last = int(g.last[t])
        position = 0
        entry = 0.0
        pnl = 0.0
        trades = 0
        for k in self.checks:
            if k + 1 > last:
                break
            want = self.signal(t, k)
            if want == position:
                continue
            fill = g.open[t, k + 1]
            if position != 0:            # close the current side
                exit_price = fill - position * p.slippage_per_share
                pnl += position * shares * (exit_price - entry)
                pnl -= shares * p.commission_per_share
            if want != 0:
                entry = fill + want * p.slippage_per_share
                pnl -= shares * p.commission_per_share
                trades += 1
            position = want
        if position != 0:                # market-on-close
            exit_price = g.day_close[t] - position * p.slippage_per_share
            pnl += position * shares * (exit_price - entry)
            pnl -= shares * p.commission_per_share
        return DayOutcome(pnl, trades, lev if trades else 0.0)

    def diagnostics(self) -> dict:
        return {"days_skipped_no_history": self.days_skipped}


__all__ = ["NoiseBand", "NoiseBandParams", "SessionGrid"]
