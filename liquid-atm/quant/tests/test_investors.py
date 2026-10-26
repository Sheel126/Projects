"""The Phase 3b investor strategies (lesson 03b §3-§4).

Each stock strategy gets a small synthetic market in which exactly the names that should pass its
rules do, so the tests read as the rules themselves. The engine-level tests check the two things
that decide whether results can be trusted: no look-ahead (truncation invariance) and orders that
respect cash and the tax reserve.
"""

from decimal import Decimal

import numpy as np
import pytest

from liquid_atm_quant.backtest.engine import BacktestConfig, Backtester
from liquid_atm_quant.backtest.fundamentals import Fundamentals
from liquid_atm_quant.backtest.strategy import PortfolioSnapshot
from liquid_atm_quant.investors.assets import AllWeather, Sleeves, TurtleParams, TurtleTrend
from liquid_atm_quant.investors.base import TargetBook
from liquid_atm_quant.investors.screen import keep_then_fill
from liquid_atm_quant.investors.stocks import (BuffettQuality, Canslim, CanslimParams,
                                               GreenblattMagic, LynchPeg, TempletonParams,
                                               TempletonValue)
from synth import bars, panel, trend
from synth_fundamentals import LATER_ENDS, QUARTER_ENDS, company

D = Decimal
N = 300
T = 100            # a session in May 2020: fundamentals live, 63+ sessions of history
LATE = QUARTER_ENDS[2:] + LATER_ENDS[4:6]
"""Eight quarters to mid-2020: still live at the late-2020 sessions that 252-day lookbacks need."""


def flat(price: float = 50.0, n: int = N) -> list[tuple]:
    return bars(np.full(n, price) * np.where(np.arange(n) % 2, 1.001, 0.999), volume=1_000_000)


def snapshot_book(view, positions: dict[str, D] | None = None, cash: D = D("100000"),
                  reserve: D = D("0")) -> PortfolioSnapshot:
    positions = positions or {}
    equity = cash + sum(q * D(str(view.latest("close", s))) for s, q in positions.items())
    return PortfolioSnapshot(view.today, equity, cash, cash - reserve, positions, frozenset())


# ---- the order adapter --------------------------------------------------------------------

def test_sells_come_before_buys_and_the_tax_reserve_is_not_invested():
    p = panel({"A": flat(), "B": flat()})
    view = p.view(10)
    book = snapshot_book(view, {"A": D(1000)}, cash=D("50000"), reserve=D("10000"))
    orders = TargetBook(band=0.5).orders({"B": 1.0}, view, book)
    assert [o.symbol for o in orders] == ["A", "B"]
    assert orders[0].weight == 0
    # equity = 50k cash + ~50k of A = ~100k; 10k reserved -> 98% of 90% invested
    assert float(orders[1].weight) == pytest.approx(0.98 * 0.9, rel=0.01)


def test_a_holding_inside_the_band_is_left_alone():
    p = panel({"A": flat(), "B": flat()})
    view = p.view(10)
    book = snapshot_book(view, {"A": D(1000)}, cash=D("50000"))        # A is ~50%
    assert TargetBook(band=0.5).orders({"A": 0.6}, view, book) == []
    assert len(TargetBook(band=0.1).orders({"A": 0.6}, view, book)) == 1
    never = TargetBook(band=float("inf"), overrides={"B": 0.1})
    assert never.orders({"A": 0.9}, view, book) == []


def test_hysteresis_keeps_a_holding_until_it_drops_past_the_hold_rank():
    ranked = [f"S{i}" for i in range(10)]
    sectors = {s: "Tech" for s in ranked}
    assert keep_then_fill(ranked, {"S7"}, n=3, hold_rank=8, sectors=sectors,
                          per_sector=None) == ["S7", "S0", "S1"]
    assert keep_then_fill(ranked, {"S9"}, n=3, hold_rank=8, sectors=sectors,
                          per_sector=None) == ["S0", "S1", "S2"]
    capped = keep_then_fill(ranked, set(), n=3, hold_rank=8, sectors=sectors, per_sector=2)
    assert capped == ["S0", "S1"]


# ---- the stock strategies -----------------------------------------------------------------

def market(names: list[str], prices: dict[str, list[tuple]] | None = None):
    series = {s: (prices or {}).get(s, flat()) for s in names}
    series.setdefault("SPY", bars(trend(N, 300.0, 0.0005, 0.003), volume=50_000_000))
    return panel(series, members=set(names))


def test_buffett_buys_high_roic_low_debt_steady_earners_cheapest_first():
    rows = (company("GOOD")                                   # ROIC ~23%, EY ~12%
            + company("RICH", shares=3e6)                     # same business at 3x the price
            + company("DEBT", debt=40e6)                      # debt/equity 2.0
            + company("LUMPY", ni=[1e6, -1e6, 1e6, -1e6, 1e6, 1e6, 1e6, 1e6])
            + company("POOR", ni=0.2e6))                      # ROIC ~5%
    names = ["GOOD", "RICH", "DEBT", "LUMPY", "POOR"]
    strat = BuffettQuality(Fundamentals(rows), {s: "Industrials" for s in names})
    view = market(names).view(T)
    weights = strat.targets(view, snapshot_book(view))
    assert strat.selected == ["GOOD", "RICH"]                 # ranked by earnings yield
    assert weights == {"GOOD": 0.5, "RICH": 0.5}


def test_buffett_skips_banks_and_utilities():
    rows = company("BANK") + company("GOOD")
    strat = BuffettQuality(Fundamentals(rows), {"BANK": "Financials", "GOOD": "Industrials"})
    view = market(["BANK", "GOOD"]).view(T)
    strat.targets(view, snapshot_book(view))
    assert strat.selected == ["GOOD"]


def test_greenblatt_ranks_on_return_on_capital_plus_earnings_yield():
    rows = (company("BOTH")                                   # good on both
            + company("ROC", shares=4e6)                      # great ROC, expensive
            + company("CHEAP", ppe=80e6)                      # cheap, capital-heavy
            + company("LOSS", ni=-1e6))
    names = ["BOTH", "ROC", "CHEAP", "LOSS"]
    strat = GreenblattMagic(Fundamentals(rows), {s: "Industrials" for s in names})
    view = market(names).view(T)
    strat.targets(view, snapshot_book(view))
    assert strat.selected[0] == "BOTH" and "LOSS" not in strat.selected


def test_lynch_wants_growth_at_a_reasonable_price():
    grow = [1e6] * 4 + [1.25e6] * 4                           # +25%/yr, P/E 10 -> PEG 0.4
    rows = (company("GARP", ni=grow)
            + company("PRICEY", ni=grow, shares=4e6)          # P/E 40 -> PEG 1.6
            + company("STALL")                                # no growth
            + company("ROCKET", ni=[1e6] * 4 + [3e6] * 4))    # +200%: distrusted
    names = ["GARP", "PRICEY", "STALL", "ROCKET"]
    strat = LynchPeg(Fundamentals(rows), {s: "Industrials" for s in names})
    view = market(names).view(T)
    strat.targets(view, snapshot_book(view))
    assert strat.selected == ["GARP"]


def leader(n: int = N) -> list[tuple]:
    return bars(trend(n, 20.0, 0.004, 0.002), volume=2_000_000)


def test_canslim_buys_accelerating_leaders_near_highs_and_cuts_losses():
    accel = [1e6] * 4 + [1.3e6, 1.4e6, 1.5e6, 1.6e6]          # every quarter +30-60% y/y
    names = ["LEAD"] + [f"LAG{i}" for i in range(9)]
    rows = company("LEAD", ni=accel, ends=LATE)
    rows += sum((company(s, ends=LATE) for s in names[1:]), [])             # no acceleration
    prices = {"LEAD": leader()}
    strat = Canslim(Fundamentals(rows), {s: "Tech" for s in names}, CanslimParams())
    p = market(names, prices)
    view = p.view(255)
    weights = strat.targets(view, snapshot_book(view))
    assert strat.selected == ["LEAD"] and weights == {"LEAD": pytest.approx(1 / 15)}

    # an 8% fall from the selection price is sold the next close it is seen (mid-month: the
    # stop does not wait for the monthly refresh)
    strat._reference["LEAD"] *= 1.10
    assert p.sessions[256].month == p.sessions[255].month
    view = p.view(256)
    assert strat.targets(view, snapshot_book(view)) == {}


def test_canslim_goes_to_cash_when_the_market_turns_down():
    names = ["LEAD"]
    falling = bars(trend(N, 300.0, -0.002, 0.003), volume=50_000_000)
    p = panel({"LEAD": leader(), "SPY": falling}, members={"LEAD"})
    strat = Canslim(Fundamentals(company("LEAD", ni=[1e6] * 4 + [2e6] * 4, ends=LATE)),
                    {"LEAD": "Tech"})
    strat.selected, strat._reference = ["LEAD"], {"LEAD": 1.0}
    view = p.view(260)
    assert strat.targets(view, snapshot_book(view)) == {}
    assert strat.selected == []


def crash(n: int = N, at: int = 200, depth: float = 0.5) -> list[tuple]:
    closes = np.r_[np.full(at, 100.0), np.full(n - at, 100.0 * (1 - depth))]
    return bars(closes * np.where(np.arange(n) % 2, 1.001, 0.999), volume=1_000_000)


def test_templeton_buys_profitable_companies_after_a_crash_and_parks_the_rest_in_spy():
    names = ["HATED", "BROKE", "FINE"]
    rows = (company("HATED", shares=0.4e6, ends=LATE)
            + company("BROKE", ni=-1e6, shares=0.4e6, ends=LATE) + company("FINE", ends=LATE))
    params = TempletonParams(high_lookback=150)
    strat = TempletonValue(Fundamentals(rows), {s: "Industrials" for s in names}, params)
    p = market(names, {"HATED": crash(), "BROKE": crash()})
    view = p.view(220)
    weights = strat.targets(view, snapshot_book(view))
    assert strat.selected == ["HATED"]
    assert weights == {"HATED": pytest.approx(1 / 20), "SPY": pytest.approx(19 / 20)}


# ---- the cross-asset strategies -----------------------------------------------------------

def test_turtle_enters_on_a_55_day_high_exits_on_a_20_day_low_and_parks_cash_in_shy():
    up = trend(150, 100.0, 0.003, 0.001)
    down = up[-1] * (1 - 0.004) ** np.arange(1, 101)
    p = panel({"GLD": bars(np.r_[up, down], range_pct=0.0005), "SHY": flat(80.0, 250)})
    strat = TurtleTrend(TurtleParams(assets=("GLD",)))
    book = snapshot_book(p.view(0))
    first = strat.targets(p.view(60), book)
    assert set(first) == {"GLD", "SHY"} and first["GLD"] <= 0.20
    assert strat.targets(p.view(61), book) is None            # nothing new: no orders
    exits = [t for t in range(151, 250) if strat.targets(p.view(t), book) is not None]
    assert exits and "GLD" not in strat.weights


def test_all_weather_holds_its_mix_through_the_engine():
    p = panel({s: flat(100.0) for s in ("SPY", "TLT", "IEF", "GLD", "DBC")})
    result = Backtester(p, BacktestConfig()).run(AllWeather())
    last = result.equity.iloc[-2]
    assert last["n_positions"] == 5
    assert float(last["cash"]) / float(last["equity"]) < 0.05


def test_sleeves_add_up_their_children():
    p = panel({s: flat(100.0) for s in ("SPY", "TLT", "IEF", "GLD", "DBC", "SHY")})
    combo = Sleeves([(AllWeather(), 0.5), (TurtleTrend(TurtleParams(assets=("GLD",))), 0.5)],
                    name="combo")
    weights = combo.targets(p.view(60), snapshot_book(p.view(60)))
    assert weights["TLT"] == pytest.approx(0.2) and weights["SHY"] == pytest.approx(0.5)
    assert combo.params.children["all_weather"]["band"] == 0.2


# ---- look-ahead ---------------------------------------------------------------------------

def test_a_stock_strategy_cannot_see_the_future():
    """Run on the full panel and on its first k sessions: every shared session must match."""
    names = ["GOOD", "RICH", "POOR"]
    rows = company("GOOD") + company("RICH", shares=3e6) + company("POOR", ni=0.2e6)
    p = market(names, {"GOOD": leader(), "RICH": crash(at=180, depth=0.3)})
    sectors = {s: "Industrials" for s in names}
    full = Backtester(p, BacktestConfig()).run(BuffettQuality(Fundamentals(rows), sectors))
    k = 150
    head = Backtester(p.head(k), BacktestConfig()).run(BuffettQuality(Fundamentals(rows), sectors))
    a = full.equity.iloc[:k - 1]["equity"].astype(float).to_numpy()
    b = head.equity.iloc[:k - 1]["equity"].astype(float).to_numpy()
    assert np.allclose(a, b)
