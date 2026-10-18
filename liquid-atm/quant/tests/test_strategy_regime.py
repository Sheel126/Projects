"""The regime filter (lesson 03 §2): hysteresis and the three states."""

from types import SimpleNamespace

import numpy as np

from liquid_atm_quant.strategy.params import FunnelParams
from liquid_atm_quant.strategy.regime import Regime, RegimeFilter, trend_states

P = FunnelParams()


def test_trend_does_not_flip_inside_the_band():
    sma = np.full(6, 100.0)
    #            start up, dip inside band, below band, back inside, above band
    close = np.array([101.0, 99.5, 99.1, 98.9, 100.5, 101.1])
    assert trend_states(close, sma, 0.01).tolist() == [1, 1, 1, 0, 0, 1]


def test_trend_is_unknown_until_the_average_exists_and_holds_through_a_missing_print():
    sma = np.array([np.nan, np.nan, 100.0, 100.0, 100.0])
    close = np.array([90.0, 110.0, 105.0, np.nan, 104.0])
    assert trend_states(close, sma, 0.01).tolist() == [-1, -1, 1, 1, 1]


def reading(close, breadth, vol):
    n = len(close)
    ind = SimpleNamespace(regime_close=np.asarray(close, dtype=float),
                          regime_sma=np.full(n, 100.0), breadth=np.full(n, breadth),
                          regime_vol=np.full(n, vol))
    return RegimeFilter(ind, P).at(n - 1)


def test_all_three_healthy_is_risk_on():
    assert reading([105.0], 0.60, 0.15).state is Regime.RISK_ON


def test_narrow_breadth_or_high_vol_is_caution_not_risk_off():
    assert reading([105.0], 0.40, 0.15).state is Regime.CAUTION
    assert reading([105.0], 0.60, 0.30).state is Regime.CAUTION


def test_missing_breadth_or_vol_counts_as_unhealthy():
    assert reading([105.0], np.nan, 0.15).state is Regime.CAUTION
    assert reading([105.0], 0.60, np.nan).state is Regime.CAUTION


def test_a_downtrend_is_risk_off_whatever_breadth_and_vol_say():
    assert reading([105.0, 95.0], 0.90, 0.05).state is Regime.RISK_OFF
