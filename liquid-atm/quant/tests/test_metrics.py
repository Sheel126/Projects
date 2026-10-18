"""Metrics (lesson 02 §10). Each one is checked against a curve whose answer is known by hand."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from liquid_atm_quant.backtest.metrics import TRADING_DAYS, compute, drawdown, trade_stats
from liquid_atm_quant.backtest.engine import TradeRecord
from liquid_atm_quant.tax.money import money

D = money


def curve(values):
    days = [date(2026, 1, 5) + timedelta(days=i) for i in range(len(values))]
    return pd.Series(values, index=days, dtype=float)


def test_cagr_of_a_doubling_over_exactly_one_year():
    series = curve(np.linspace(100.0, 200.0, TRADING_DAYS))
    metrics = compute(series)
    assert metrics.years == pytest.approx(1.0, abs=0.01)
    assert metrics.cagr == pytest.approx(1.0, rel=0.02)
    assert metrics.total_return == pytest.approx(1.0)


def test_a_flat_curve_has_no_volatility_no_drawdown_and_no_calmar():
    metrics = compute(curve([100.0] * 60))
    assert metrics.volatility == 0.0
    assert metrics.sharpe == 0.0
    assert metrics.max_drawdown == 0.0
    assert np.isnan(metrics.calmar)      # no drawdown yet is not infinitely good


def test_max_drawdown_and_its_peak_and_trough():
    metrics = compute(curve([100, 120, 90, 95, 130]))
    assert metrics.max_drawdown == pytest.approx(-0.25)          # 120 -> 90
    assert metrics.max_drawdown_start == date(2026, 1, 6)        # the 120
    assert metrics.max_drawdown_end == date(2026, 1, 7)          # the 90


def test_drawdown_series_is_zero_at_every_new_high():
    dd = drawdown(curve([100, 110, 105, 120]))
    assert dd.tolist() == pytest.approx([0.0, 0.0, -110 / 120 * 0 - (1 - 105 / 110), 0.0])


def test_calmar_is_cagr_over_max_drawdown():
    metrics = compute(curve(list(np.linspace(100, 150, 300)) + [120]))
    assert metrics.calmar == pytest.approx(metrics.cagr / abs(metrics.max_drawdown))


def test_a_nonzero_risk_free_rate_lowers_sharpe_and_is_recorded():
    series = curve(100 * np.cumprod(1 + np.full(300, 0.0005)))
    free = compute(series, risk_free_rate=0.0)
    costly = compute(series, risk_free_rate=0.05)
    assert costly.sharpe < free.sharpe
    assert costly.risk_free_rate == 0.05


def test_sortino_penalises_downside_dispersion_at_the_same_mean_return():
    """Both series average +0.1% a day. The one whose down days are worse scores lower."""
    mild = curve(100 * np.cumprod(1 + np.tile([0.003, -0.001], 100)))
    severe = curve(100 * np.cumprod(1 + np.tile([0.011, -0.009], 100)))
    assert compute(mild).sortino > compute(severe).sortino


def test_no_downside_at_all_is_nan_not_a_winning_score():
    """NaN, never infinity: an infinity would silently win Phase 4's parameter ranking."""
    smooth = curve(100 * np.cumprod(1 + np.full(200, 0.001)))
    assert np.isnan(compute(smooth).sortino)


def test_too_few_points_is_an_error_not_a_zero():
    with pytest.raises(ValueError):
        compute(curve([100.0]))


# ---- trade statistics ------------------------------------------------------------------------

def record(pnl, reason="take_profit", ambiguous=False, touched=False, disallowed=0, days=5):
    return TradeRecord(symbol="AAA", entry_date=date(2026, 1, 5), entry_price=D(100), qty=D(10),
                       exit_date=date(2026, 1, 12), exit_price=D(110), exit_reason=reason,
                       ambiguous_bar=ambiguous, touched_only_entry=touched, days_held=days,
                       gross_pnl=D(pnl), disallowed_loss=D(disallowed))


def test_trade_stats_on_a_known_set():
    stats = trade_stats([record(300), record(100), record(-200, "stop_loss")])
    assert stats.n_trades == 3
    assert stats.hit_rate == pytest.approx(2 / 3)
    assert stats.avg_win == 200.0
    assert stats.avg_loss == -200.0
    assert stats.profit_factor == pytest.approx(2.0)
    assert stats.exit_reasons == {"stop_loss": 1, "take_profit": 2}


def test_the_ambiguous_and_touch_shares_are_surfaced():
    """If either share is high, the result is mostly an artefact of a modelling choice."""
    stats = trade_stats([record(100, ambiguous=True, touched=True), record(-50, "stop_loss")])
    assert stats.ambiguous_share == 0.5
    assert stats.touch_entry_share == 0.5


def test_wash_sale_trades_are_counted():
    stats = trade_stats([record(-100, "stop_loss", disallowed=100), record(50)])
    assert stats.wash_sale_trades == 1


def test_no_closed_trades_gives_zeros_rather_than_an_error():
    assert trade_stats([]).n_trades == 0
    open_only = record(0)
    open_only.exit_date = None
    assert trade_stats([open_only]).n_trades == 0
