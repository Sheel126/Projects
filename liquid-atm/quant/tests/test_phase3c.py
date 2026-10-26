"""Phase 3c strategies (lesson 03c): cap weighting, the trend switch and the engine warm-up."""

from decimal import Decimal

import numpy as np
import pytest

from liquid_atm_quant.backtest.engine import BacktestConfig, Backtester
from liquid_atm_quant.backtest.fundamentals import Fundamentals
from liquid_atm_quant.investors.assets import TrendSwitch
from liquid_atm_quant.investors.stocks import BuffettQualityCap, capped_weights
from synth import bars, panel, trend
from synth_fundamentals import company
from test_investors import T, market, snapshot_book

D = Decimal


def test_capped_weights_follow_size_and_redistribute_the_excess():
    w = capped_weights({"BIG": 90.0, "A": 5.0, "B": 5.0}, cap=0.5)
    assert w == {"BIG": 0.5, "A": pytest.approx(0.25), "B": pytest.approx(0.25)}
    w = capped_weights({f"S{i}": float(i + 1) for i in range(20)}, cap=0.10)
    assert sum(w.values()) == pytest.approx(1.0) and max(w.values()) <= 0.10 + 1e-12
    assert w["S0"] < w["S5"]


def test_cap_weighted_quality_picks_the_same_names_but_weights_by_size():
    rows = company("GOOD") + company("RICH", shares=3e6) + company("POOR", ni=0.2e6)
    names = ["GOOD", "RICH", "POOR"]
    strat = BuffettQualityCap(Fundamentals(rows), {s: "Industrials" for s in names})
    view = market(names).view(T)
    weights = strat.targets(view, snapshot_book(view))
    assert strat.selected == ["GOOD", "RICH"]
    # same price, RICH has 3x the shares -> 3x the cap; the 10% cap binds on both and the
    # leftover budget has nowhere to go, so the weights are the cap
    assert weights == {"GOOD": pytest.approx(0.1), "RICH": pytest.approx(0.1)}


def test_trend_switch_holds_spy_above_its_average_and_shy_below():
    up = trend(260, 100.0, 0.002, 0.001)
    down = up[-1] * (1 - 0.003) ** np.arange(1, 141)
    p = panel({"SPY": bars(np.r_[up, down], volume=50_000_000),
               "SHY": bars(np.full(400, 80.0), volume=5_000_000)})
    strat = TrendSwitch()
    book = snapshot_book(p.view(0))
    held = []
    for t in range(200, 400):
        w = strat.targets(p.view(t), book)
        if w:
            held.append(next(iter(w)))
    assert held[0] == "SPY" and held[-1] == "SHY"
    assert strat.diagnostics()["switches"] == len(held) - 1


def test_warm_up_sessions_are_readable_but_never_traded():
    p = panel({"SPY": bars(trend(300, 100.0, 0.001, 0.002), volume=50_000_000),
               "SHY": bars(np.full(300, 80.0), volume=5_000_000)})
    start = p.sessions[220]
    result = Backtester(p, BacktestConfig()).run(TrendSwitch(), start)
    assert result.equity.index[0] == start
    assert result.trades == [] or all(t.entry_date > start for t in result.trades)
    assert float(result.equity["n_positions"].iloc[-1]) == 1     # bought SPY right away


# ---- vol target x trend -------------------------------------------------------------------

from liquid_atm_quant.investors.assets import (VigilantAssetAllocation, VolTargetTrend,  # noqa: E402
                                               VolTargetTrendV2, VolTrendV2Params)


def calm_then_wild(n: int = 400) -> np.ndarray:
    rng = np.random.default_rng(7)
    rets = np.r_[rng.normal(0.0008, 0.004, 300), rng.normal(0.0008, 0.03, n - 300)]
    return 100 * np.exp(np.cumsum(rets))


def test_vol_trend_levers_up_when_calm_and_cuts_when_volatile():
    p = panel({"SPY": bars(calm_then_wild(), volume=50_000_000)})
    strat = VolTargetTrend()
    calm, wild = strat.exposure(p.view(290)), strat.exposure(p.view(330))
    assert calm == pytest.approx(1.5)                  # ~6% vol -> capped at 1.5x
    assert wild < 0.5
    assert strat.weights(1.25) == {"SPY": 0.75, "SSO": 0.25}
    assert strat.weights(0.5) == {"SPY": 0.5, "BIL": 0.5}


def test_vol_trend_is_flat_below_the_200_day_average():
    falling = 100 * 0.998 ** np.arange(300)
    p = panel({"SPY": bars(falling, volume=50_000_000)})
    assert VolTargetTrend().exposure(p.view(299)) == 0.0


def test_stepped_exposure_has_hysteresis():
    s = VolTargetTrend()
    assert s.stepped(1.10) == 1.0
    assert s.stepped(1.24) == 1.0 and s.stepped(0.90) == 1.0     # within half a step below
    assert s.stepped(0.86) == 0.75                                # more than half a step below
    assert s.stepped(0.99) == 0.75                                # up needs a whole step
    assert s.stepped(1.0) == 1.0
    assert s.stepped(0.0) == 0.0                                  # filter off: straight to zero


def test_symmetric_forecast_re_levers_faster_than_the_asymmetric_one():
    rng = np.random.default_rng(3)
    rets = np.r_[rng.normal(0.0, 0.03, 40), rng.normal(0.0, 0.005, 25)]
    v1, v2 = VolTargetTrend(), VolTargetTrendV2()
    assert v2.forecast_vol(rets) < v1.forecast_vol(rets) / 2


def test_wash_aware_buying_uses_the_twin_and_waits_out_a_blacklisted_sso():
    s = VolTargetTrendV2(VolTrendV2Params(wash_aware=True))
    s._held = {"SPY": 0.5}
    assert s._fill(["SPY", "VTI"], 0.75, frozenset({"SPY"})) == {"SPY": 0.5, "VTI": 0.25}
    s._held = {"SPY": 0.5, "VTI": 0.25}
    assert s._fill(["SPY", "VTI"], 0.6, frozenset()) == pytest.approx({"SPY": 0.5, "VTI": 0.1})
    s._held = {"SSO": 0.25}
    assert s._fill(["SSO"], 0.5, frozenset({"SSO"})) == {"SSO": 0.25}
    assert s.diagnostics()["deferred_for_wash_sale"] == 1


def test_vaa_steps_aside_when_any_risky_asset_has_negative_momentum():
    up = bars(100 * 1.001 ** np.arange(300), volume=5_000_000)
    down = bars(100 * 0.999 ** np.arange(300), volume=5_000_000)
    safe = bars(80 * 1.0002 ** np.arange(300), volume=5_000_000)
    series = {"SPY": up, "EFA": up, "EEM": down, "AGG": up, "LQD": safe, "IEF": safe,
              "SHY": bars(np.full(300, 80.0), volume=5_000_000)}
    p = panel(series)
    w = VigilantAssetAllocation().targets(p.view(299), snapshot_book(p.view(299)))
    assert set(w) <= {"LQD", "IEF"}
