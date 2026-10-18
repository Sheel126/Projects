"""The baselines, and the engine self-test they exist to provide (lesson 02 §9).

On a synthetic panel whose compound growth is known in closed form, buy-and-hold through the full
engine must reproduce it to the cent. That is the same check `scripts/run_backtest.py` performs
against real SPY data, done here without needing a database.
"""

from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from liquid_atm_quant.backtest.engine import BacktestConfig, Backtester
from liquid_atm_quant.backtest.metrics import compute
from liquid_atm_quant.backtest.panel import Panel
from liquid_atm_quant.baselines import BuyAndHold, NaiveMomentum
from liquid_atm_quant.backtest.costs import ZERO_COSTS
from liquid_atm_quant.tax.ledger import TaxConfig

D = Decimal
NO_TAX = TaxConfig(short_term_rate=D("0"), long_term_rate=D("0"), qualified_dividend_rate=D("0"),
                   payment_schedule="none")


def sessions(n):
    out, day = [], date(2020, 1, 2)
    while len(out) < n:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def panel_of(prices: dict[str, list[float]], factors: dict[str, list[float]] | None = None) -> Panel:
    n = max(len(v) for v in prices.values())
    days = sessions(n)
    rows = []
    for symbol, series in prices.items():
        f = (factors or {}).get(symbol, [1.0] * len(series))
        for i, price in enumerate(series):
            rows.append({"trade_date": days[i], "symbol": symbol, "open": price, "high": price,
                         "low": price, "close": price, "volume": 50_000_000,
                         "adj_factor": f[i], "segment_id": 0})
    return Panel.from_frame(pd.DataFrame(rows), days)


# ---- buy and hold ----------------------------------------------------------------------------

def test_buy_and_hold_reproduces_a_known_compound_path_exactly():
    """The engine self-test: 0.05% a day for 500 sessions is a known number, to the cent."""
    n, daily = 500, 1.0005
    prices = [100.0 * daily ** i for i in range(n)]
    panel = panel_of({"SPY": prices})
    config = BacktestConfig(initial_cash=D("1000000.00"), costs=ZERO_COSTS, tax=NO_TAX,
                            apply_dividends=False, liquidate_at_end=False,
                            allow_fractional=True)
    result = Backtester(panel, config).run(BuyAndHold("SPY"))

    # Bought at session 1's open with the whole account, so equity tracks the price from there.
    entry, final = prices[1], prices[-1]
    expected = D("1000000.00") * D(repr(final)) / D(repr(entry))
    # To the cent: the only rounding allowed is the final quantization of the equity total.
    assert abs(float(result.final_equity) - float(expected)) <= 0.01

    # rel=1e-7 because the curve itself is stored in cents: on a $1M account that is the floor on
    # how precisely a return can be recovered from it.
    measured = compute(result.equity["equity"].iloc[1:])
    assert measured.total_return == pytest.approx(final / entry - 1, rel=1e-7)
    assert measured.max_drawdown == 0.0


def test_buy_and_hold_never_realizes_a_gain_until_the_terminal_liquidation():
    prices = [100.0 + i for i in range(200)]
    panel = panel_of({"SPY": prices})
    config = BacktestConfig(initial_cash=D("100000.00"), costs=ZERO_COSTS, apply_dividends=False,
                            liquidate_at_end=True, allow_fractional=True,
                            tax=TaxConfig(short_term_rate=D("0.32"), long_term_rate=D("0.15"),
                                          payment_schedule="quarterly"))
    result = Backtester(panel, config).run(BuyAndHold("SPY"))

    # The equity curve covers the holding period; the terminal liquidation happens after its last
    # row, which is exactly why the two have to be read separately.
    assert (result.equity["reserve"] == 0).all()             # nothing realized while holding
    assert (result.equity["tax_paid_cum"] == 0).all()        # so nothing was ever paid
    assert result.terminal["terminal_tax"] > 0
    # Held under a year in this window, so the deferred bill comes due at the short-term rate.
    gain = float(result.terminal["cash_after_liquidation"]) - 100000.0
    assert float(result.terminal["terminal_tax"]) == pytest.approx(gain * 0.32, rel=1e-3)


def test_a_long_hold_settles_at_the_long_term_rate():
    """Over two years, buy-and-hold's terminal bill is long-term - the benchmark's real advantage."""
    prices = [100.0 + i * 0.1 for i in range(600)]
    panel = panel_of({"SPY": prices})
    config = BacktestConfig(initial_cash=D("100000.00"), costs=ZERO_COSTS, apply_dividends=False,
                            liquidate_at_end=True, allow_fractional=True,
                            tax=TaxConfig(short_term_rate=D("0.32"), long_term_rate=D("0.15"),
                                          payment_schedule="quarterly"))
    result = Backtester(panel, config).run(BuyAndHold("SPY"))
    gain = float(result.terminal["cash_after_liquidation"]) - 100000.0
    assert float(result.terminal["terminal_tax"]) == pytest.approx(gain * 0.15, rel=1e-3)


def test_dividends_on_a_long_hold_are_qualified_and_taxed_yearly():
    """The drag the benchmark really pays, and the bot mostly does not."""
    n = 400
    prices = [100.0] * n
    # Two 0.5% distributions, at sessions 100 and 300.
    factors = []
    for i in range(n):
        step = 1.0
        if i < 100:
            step *= 0.995
        if i < 300:
            step *= 0.995
        factors.append(step)
    panel = panel_of({"SPY": prices}, {"SPY": factors})
    config = BacktestConfig(initial_cash=D("100000.00"), costs=ZERO_COSTS, apply_dividends=True,
                            liquidate_at_end=False, allow_fractional=True,
                            tax=TaxConfig(short_term_rate=D("0.32"),
                                          qualified_dividend_rate=D("0.15"),
                                          payment_schedule="none"))
    result = Backtester(panel, config).run(BuyAndHold("SPY"))
    assert result.diagnostics["dividends"] == 2
    assert result.ledger.dividends_received > 0
    # Qualified rate, because the position is held well past 61 days before each ex-date. The two
    # distributions fall in different tax years and each year's tax is rounded to cents on its own,
    # so the total can differ from rounding the combined figure by a penny.
    expected = (result.ledger.dividends_received * D("0.15")).quantize(D("0.01"))
    assert abs(result.equity["reserve"].iloc[-1] - expected) <= D("0.02")


# ---- naive momentum --------------------------------------------------------------------------

def test_naive_momentum_buys_the_strongest_names_and_rotates_monthly():
    n = 320
    # WIN rises fastest, MID slower, LOSE falls. Only the top two should ever be held.
    prices = {"WIN": [100.0 * 1.002 ** i for i in range(n)],
              "MID": [100.0 * 1.0005 ** i for i in range(n)],
              "LOSE": [100.0 * 0.999 ** i for i in range(n)]}
    panel = panel_of(prices)
    config = BacktestConfig(initial_cash=D("100000.00"), costs=ZERO_COSTS, tax=NO_TAX,
                            apply_dividends=False, liquidate_at_end=False, max_positions=2)
    result = Backtester(panel, config).run(NaiveMomentum(top_n=2, min_dollar_volume=0.0))

    held = set(result.ledger.book.lots[i].symbol for i in range(len(result.ledger.book.lots)))
    assert held == {"WIN", "MID"}
    assert "LOSE" not in held
    assert result.final_equity > D("100000.00")


def test_momentum_needs_a_full_lookback_before_it_trades():
    """No ranking on partial history: a 12-1 window is 273 sessions, and short of that it waits."""
    panel = panel_of({"AAA": [100.0 + i for i in range(100)],
                      "BBB": [100.0 - i * 0.1 for i in range(100)]})
    config = BacktestConfig(initial_cash=D("100000.00"), costs=ZERO_COSTS, tax=NO_TAX,
                            apply_dividends=False, liquidate_at_end=False)
    result = Backtester(panel, config).run(NaiveMomentum(min_dollar_volume=0.0))
    assert result.diagnostics["entries_filled"] == 0
    assert result.final_equity == D("100000.00")


def test_the_price_and_liquidity_floors_exclude_a_name_that_would_rank_first():
    """Both floors read RAW prices and real dollar volume, never adjusted levels (lesson 01 §2)."""
    n = 320
    prices = {"BIG": [100.0 * 1.002 ** i for i in range(n)],
              "PENNY": [1.0 * 1.004 ** i for i in range(n)],     # strongest, but under $10
              "THIN": [200.0 * 1.003 ** i for i in range(n)]}    # strong, but barely trades
    days = sessions(n)
    rows = []
    for symbol, series in prices.items():
        volume = 10.0 if symbol == "THIN" else 50_000_000.0
        for i, price in enumerate(series):
            rows.append({"trade_date": days[i], "symbol": symbol, "open": price, "high": price,
                         "low": price, "close": price, "volume": volume, "adj_factor": 1.0,
                         "segment_id": 0})
    panel = Panel.from_frame(pd.DataFrame(rows), days)

    strategy = NaiveMomentum(top_n=1, min_price=D("10.00"), min_dollar_volume=5_000_000.0)
    view = panel.view(300)
    raw_ranking = sorted(((s, prices[s][300] / prices[s][0]) for s in prices),
                         key=lambda r: r[1], reverse=True)
    assert raw_ranking[0][0] == "PENNY"                 # it really is the strongest performer
    assert view.latest("close", "PENNY") < 10.0         # and it really is under the price floor

    eligible = dict(strategy._rank(view))
    assert "PENNY" not in eligible                       # excluded by the price floor
    assert "THIN" not in eligible                        # excluded by the liquidity floor
    assert set(eligible) == {"BIG"}


def test_momentum_ranking_uses_adjusted_prices_not_raw_levels():
    """A 4-for-1 split must not read as a 75% crash (lesson 01 §2)."""
    n = 320
    split_at = 280
    raw = [400.0 * 1.001 ** i for i in range(split_at)] + \
          [100.0 * 1.001 ** i for i in range(split_at, n)]
    factors = [0.25] * split_at + [1.0] * (n - split_at)
    steady = [100.0 * 1.0002 ** i for i in range(n)]
    panel = panel_of({"SPLIT": raw, "STEADY": steady}, {"SPLIT": factors})

    view = panel.view(n - 1)
    ranked = dict(NaiveMomentum(min_dollar_volume=0.0)._rank(view))
    # On adjusted prices SPLIT compounded at 0.1%/session and beats STEADY; on raw levels it would
    # look like a catastrophic loss and rank last.
    assert ranked["SPLIT"] > ranked["STEADY"] > 0
