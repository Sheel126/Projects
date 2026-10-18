"""Whole-panel indicator matrices, computed once per run (lesson 03 §7).

The funnel screens every name every day. Doing that with a per-symbol loop over `DataView`
slices would cost minutes per run, and Phase 4 needs hundreds of runs, so each indicator here is
one vectorised `[session, symbol]` matrix and the strategy reads row `t`.

That bypasses the `DataView` cursor, so it is only safe if every matrix is **causal**: row `t`
must depend on rows `<= t` and nothing else. Rolling windows and a forward-running EWM are; a
centred window, a backfill or a full-sample normalisation is not. The guarantee is enforced by
`test_strategy_indicators.py::test_every_indicator_is_truncation_invariant`, not by review.

Conventions, inherited from lessons 01 and 02:

* Shapes and trends use **adjusted** prices, so a split is not a crash.
* Anything that becomes an order price is on the **raw** scale. ATR is computed on adjusted bars
  and divided by today's `adj_factor`; factor changes after `t` scale the whole window equally and
  cancel, so this is causal whichever way the adjustment is anchored.
* Volume ratios use **dollar** volume (`raw close × raw volume`), which a split leaves unchanged.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from liquid_atm_quant.backtest.panel import Panel
from liquid_atm_quant.strategy.params import FunnelParams

_CACHE_ATTR = "_funnel_indicators"


def _frame(x: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(x, copy=False)


def sma(x: np.ndarray, window: int) -> np.ndarray:
    """Trailing mean. Any missing value inside the window makes the result NaN."""
    return _frame(x).rolling(window, min_periods=window).mean().to_numpy()


def rolling_max(x: np.ndarray, window: int) -> np.ndarray:
    return _frame(x).rolling(window, min_periods=window).max().to_numpy()


def shift(x: np.ndarray, n: int = 1) -> np.ndarray:
    out = np.full_like(x, np.nan, dtype=np.float64)
    out[n:] = x[:-n]
    return out


def wilder(x: np.ndarray, window: int) -> np.ndarray:
    """Wilder's smoothing: an EWM with alpha = 1/window, run forward from each column's start."""
    return _frame(x).ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean().to_numpy()


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    prev = shift(close)
    with np.errstate(invalid="ignore"):
        # fmax ignores a NaN operand, so a bar with no previous close falls back to high - low.
        return np.fmax(high - low, np.fmax(np.abs(high - prev), np.abs(low - prev)))


def run_length(segment_id: np.ndarray) -> np.ndarray:
    """Consecutive sessions, up to and including `t`, with a bar from one corporate identity.

    A missing bar or a change of segment resets the count. The screener requires this to cover
    the longest lookback, which is the matrix form of `DataView.same_segment` (lesson 01 §5b).
    """
    out = np.zeros(segment_id.shape, dtype=np.int32)
    present = segment_id >= 0
    out[0] = present[0]
    for t in range(1, len(segment_id)):
        same = present[t] & (segment_id[t] == segment_id[t - 1])
        out[t] = np.where(same, out[t - 1] + 1, present[t].astype(np.int32))
    return out


@dataclass(frozen=True)
class Indicators:
    """Every matrix the regime filter and screener read. All `[session, symbol]`."""

    close: np.ndarray            # raw
    adj_close: np.ndarray
    adj_factor: np.ndarray
    run: np.ndarray
    adv: np.ndarray              # trailing mean dollar volume, including today
    sma_short: np.ndarray
    sma_fast: np.ndarray
    sma_slow: np.ndarray
    atr_adj: np.ndarray
    momentum: np.ndarray         # window return / (daily vol * sqrt(window))
    prior_high: np.ndarray       # highest adjusted close of the previous N sessions
    rvol: np.ndarray             # today's dollar volume / previous N sessions' average
    breadth: np.ndarray          # 1-D: share of today's members above their own breadth SMA
    regime_close: np.ndarray     # 1-D, adjusted
    regime_sma: np.ndarray       # 1-D
    regime_vol: np.ndarray       # 1-D, annualised realised vol

    def atr_raw(self, t: int) -> np.ndarray:
        """Row `t` of ATR on today's raw price scale: what a stop distance is measured in."""
        return self.atr_adj[t] / self.adj_factor[t]

    @classmethod
    def compute(cls, panel: Panel, p: FunnelParams) -> "Indicators":
        close = panel.column("close")
        adj = panel.column("adj_factor")
        ac, ah, al = panel.adjusted("close"), panel.adjusted("high"), panel.adjusted("low")

        with np.errstate(invalid="ignore", divide="ignore"):
            dollar = close * panel.column("volume")
            adv = _frame(dollar).rolling(p.adv_window, min_periods=1).mean().to_numpy()
            prev_dollar = shift(sma(dollar, p.rvol_window))
            rvol = dollar / prev_dollar

            log_ret = np.log(ac / shift(ac))
            vol = _frame(log_ret).rolling(p.momentum_window,
                                          min_periods=p.momentum_window).std().to_numpy()
            ret = ac / shift(ac, p.momentum_window) - 1.0
            momentum = ret / (vol * np.sqrt(p.momentum_window))

            breadth_sma = sma(ac, p.breadth_sma)
            counted = panel.member & np.isfinite(breadth_sma) & np.isfinite(ac)
            above = counted & (ac > breadth_sma)
            n = counted.sum(axis=1)
            breadth = np.where(n > 0, above.sum(axis=1) / np.maximum(n, 1), np.nan)

        j = panel.index.get(p.regime_symbol)
        if j is None:
            raise KeyError(f"regime symbol {p.regime_symbol} is not in the panel")
        spy = ac[:, j]
        spy_ret = log_ret[:, j]
        regime_vol = (pd.Series(spy_ret).rolling(p.vol_window, min_periods=p.vol_window).std()
                      .to_numpy() * np.sqrt(252))

        return cls(
            close=close, adj_close=ac, adj_factor=adj, run=run_length(panel.segment_id), adv=adv,
            sma_short=sma(ac, p.sma_short), sma_fast=sma(ac, p.sma_fast),
            sma_slow=sma(ac, p.sma_slow),
            atr_adj=wilder(true_range(ah, al, ac), p.atr_window),
            momentum=momentum, prior_high=shift(rolling_max(ac, p.breakout_window)), rvol=rvol,
            breadth=breadth, regime_close=spy,
            regime_sma=pd.Series(spy).rolling(p.trend_sma, min_periods=p.trend_sma).mean()
            .to_numpy(),
            regime_vol=regime_vol)

    @classmethod
    def for_panel(cls, panel: Panel, p: FunnelParams) -> "Indicators":
        """Cached on the panel. One entry only: Phase 4 sweeps parameters, and keeping every
        set's matrices alive would hold gigabytes for nothing."""
        key = p.fingerprint()
        cached = getattr(panel, _CACHE_ATTR, None)
        if cached is not None and cached[0] == key:
            return cached[1]
        value = cls.compute(panel, p)
        setattr(panel, _CACHE_ATTR, (key, value))
        return value

    def matrices(self) -> dict[str, np.ndarray]:
        """Name → array, for the truncation test."""
        return {name: getattr(self, name) for name in self.__dataclass_fields__}
