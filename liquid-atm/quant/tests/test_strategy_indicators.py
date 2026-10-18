"""Indicator matrices (lesson 03 §5, §7).

The test that matters is `test_every_indicator_is_truncation_invariant`. The screener reads
precomputed whole-panel matrices instead of going through the `DataView` cursor, so the cursor's
look-ahead guarantee no longer covers it. This test puts it back: for sampled sessions `t`,
every matrix computed on the panel cut off at `t` must equal row `t` of the full computation.
`test_the_truncation_test_catches_a_centred_window` proves it would notice a leak.
"""

import numpy as np
import pandas as pd
import pytest

from liquid_atm_quant.backtest.panel import Panel
from liquid_atm_quant.strategy.indicators import (Indicators, run_length, sma, true_range,
                                                  wilder)
from liquid_atm_quant.strategy.params import FunnelParams
from liquid_atm_quant.strategy.regime import RegimeFilter

import synth

SMALL = FunnelParams(trend_sma=30, breadth_sma=10, vol_window=10, history=40, sma_fast=10,
                     sma_slow=30, momentum_window=20, breakout_window=10, rvol_window=10,
                     sma_short=10, atr_window=5, adv_window=10)


def test_sma_is_a_trailing_mean_and_a_gap_blanks_the_window():
    x = np.array([[1.0], [2.0], [3.0], [np.nan], [5.0], [6.0], [7.0]])
    out = sma(x, 3)[:, 0]
    assert np.isnan(out[:2]).all()
    assert out[2] == pytest.approx(2.0)
    assert np.isnan(out[3:6]).all()          # every window containing the gap
    assert out[6] == pytest.approx(6.0)


def test_wilder_smoothing_is_an_ewm_with_alpha_one_over_n():
    out = wilder(np.array([[1.0], [2.0], [3.0], [4.0]]), 2)[:, 0]
    assert np.isnan(out[0])
    assert out[1:].tolist() == pytest.approx([1.5, 2.25, 3.125])


def test_true_range_uses_the_previous_close_and_falls_back_to_high_minus_low():
    high = np.array([[10.0], [12.0], [9.0]])
    low = np.array([[9.0], [11.0], [7.0]])
    close = np.array([[9.5], [11.5], [8.0]])
    tr = true_range(high, low, close)[:, 0]
    assert tr.tolist() == pytest.approx([1.0, 2.5, 4.5])   # gap up from 9.5; drop from 11.5


def test_run_length_resets_on_a_gap_and_on_a_new_identity():
    seg = np.array([[0], [0], [-1], [0], [0], [1], [1]], dtype=np.int32)
    assert run_length(seg)[:, 0].tolist() == [1, 2, 0, 1, 2, 1, 2]


def test_atr_is_on_todays_raw_scale_across_a_split():
    """A 2:1 split inside the window must not show up as a 50% true range."""
    days = synth.sessions(40)
    rows = []
    for i, day in enumerate(days):
        split = i >= 20
        price = 50.0 if split else 100.0
        rows.append({"trade_date": day, "symbol": "AAA", "open": price, "high": price + 1,
                     "low": price - 1, "close": price, "volume": 1e6,
                     "adj_factor": 1.0 if split else 0.5, "segment_id": 0})
        rows.append({"trade_date": day, "symbol": "SPY", "open": 300, "high": 301, "low": 299,
                     "close": 300, "volume": 1e7, "adj_factor": 1.0, "segment_id": 0})
    panel = Panel.from_frame(pd.DataFrame(rows), days)
    ind = Indicators.compute(panel, SMALL)
    j = panel.index["AAA"]
    # Adjusted bars are a constant 50 +/- 0.5 before and 50 +/- 1 after the split; nowhere a jump.
    assert np.nanmax(ind.atr_adj[:, j]) < 2.0
    # Before the split, a 1.0 adjusted range is a 2.0 range in the raw prices then trading.
    assert ind.atr_raw(15)[j] == pytest.approx(1.0 / 0.5, rel=1e-6)
    assert ind.atr_raw(39)[j] == pytest.approx(2.0, rel=0.05)


# ---- the look-ahead guarantee for the precomputed path ---------------------------------------

def random_panel(n=160, symbols=8, seed=7) -> Panel:
    """Random walks with everything that makes indicators hard: gaps, a split, a ticker change,
    and index membership that flips over time."""
    rng = np.random.default_rng(seed)
    days = synth.sessions(n)
    rows = []
    for k in range(symbols):
        name = "SPY" if k == 0 else f"S{k}"
        price = 50.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
        factor = np.where(np.arange(n) < 70, 0.5, 1.0) if k == 1 else np.ones(n)
        raw = price / factor
        segment = np.where(np.arange(n) < 90, 0, 1) if k == 2 else np.zeros(n, dtype=int)
        for i in range(n):
            if k > 0 and rng.random() < 0.03:
                continue                                       # a missing bar
            o = raw[i] * (1 + rng.normal(0, 0.005))
            rows.append({"trade_date": days[i], "symbol": name, "open": o,
                         "high": max(o, raw[i]) * 1.01, "low": min(o, raw[i]) * 0.99,
                         "close": raw[i], "volume": float(rng.integers(1e5, 1e6)),
                         "adj_factor": factor[i], "segment_id": int(segment[i])})
    panel = Panel.from_frame(pd.DataFrame(rows), days)
    panel.member = rng.random(panel.shape) < 0.8
    return panel


def first_leak(compute, panel: Panel, checks=range(45, 159, 7)) -> str | None:
    """Name of the first matrix whose row `t` changes when the panel stops at `t`."""
    full = compute(panel)
    for t in checks:
        cut = compute(panel.head(t + 1))
        for name, matrix in full.items():
            if not np.array_equal(cut[name][t], matrix[t], equal_nan=True):
                return f"{name} at t={t}"
    return None


def compute_all(panel: Panel) -> dict[str, np.ndarray]:
    ind = Indicators.compute(panel, SMALL)
    out = ind.matrices()
    out["trend_state"] = RegimeFilter(ind, SMALL).trend
    return out


def test_every_indicator_is_truncation_invariant():
    assert first_leak(compute_all, random_panel()) is None


def test_the_truncation_test_catches_a_centred_window():
    """A centred rolling mean reads five sessions ahead. The detector must say so."""
    def leaky(panel):
        close = panel.adjusted("close")
        return {"centred": pd.DataFrame(close).rolling(11, center=True).mean().to_numpy()}

    assert first_leak(leaky, random_panel()) is not None


def test_indicators_are_cached_once_per_panel_and_parameter_set():
    panel = random_panel()
    first = Indicators.for_panel(panel, SMALL)
    assert Indicators.for_panel(panel, SMALL) is first
    other = Indicators.for_panel(panel, FunnelParams(**{**SMALL.__dict__, "atr_window": 7}))
    assert other is not first
