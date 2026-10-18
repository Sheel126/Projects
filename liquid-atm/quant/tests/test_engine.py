"""The daily event loop end to end (lesson 02 §1, §3, §7).

The important test in this file is `test_a_strategy_that_reads_tomorrow_is_caught`: the engine's
look-ahead defence has to be demonstrated by a strategy that actively tries to cheat, exactly as
Phase 1 planted a look-ahead signal to prove its detector worked.
"""

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from liquid_atm_quant.backtest.costs import ZERO_COSTS, CostModel
from liquid_atm_quant.backtest.engine import BacktestConfig, Backtester
from liquid_atm_quant.backtest.panel import FutureDataError, Panel
from liquid_atm_quant.backtest.strategy import BracketIntent, TargetWeight
from liquid_atm_quant.tax.ledger import TaxConfig

D = Decimal
NO_TAX = TaxConfig(short_term_rate=D("0"), long_term_rate=D("0"), qualified_dividend_rate=D("0"),
                   payment_schedule="none")
BASE = BacktestConfig(initial_cash=D("100000.00"), costs=ZERO_COSTS, tax=NO_TAX,
                      apply_dividends=False, liquidate_at_end=False)


def sessions(n):
    out, day = [], date(2026, 1, 5)
    while len(out) < n:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def panel_from(bars: dict[str, list[tuple]], days=None) -> Panel:
    """bars: {symbol: [(open, high, low, close, volume), ...]} aligned to consecutive sessions."""
    n = max(len(v) for v in bars.values())
    days = days or sessions(n)
    rows = []
    for symbol, series in bars.items():
        for i, (o, h, l, c, v) in enumerate(series):
            rows.append({"trade_date": days[i], "symbol": symbol, "open": o, "high": h, "low": l,
                         "close": c, "volume": v, "adj_factor": 1.0, "segment_id": 0})
    return Panel.from_frame(pd.DataFrame(rows), days)


def flat(n, price=100.0, volume=10_000_000):
    return [(price, price + 0.5, price - 0.5, price, volume)] * n


class Once:
    """Places one bracket on the first session, then nothing."""

    name = "once"

    def __init__(self, intent: BracketIntent, on_session: int = 0):
        self.intent, self.on_session, self._seen = intent, on_session, 0

    def on_close(self, view, book):
        self._seen += 1
        return [self.intent] if self._seen - 1 == self.on_session else []


class HoldWeight:
    name = "hold_weight"

    def __init__(self, symbol="AAA", weight=D("1.0")):
        self.symbol, self.weight, self._done = symbol, weight, False

    def on_close(self, view, book):
        if self._done:
            return []
        self._done = True
        return [TargetWeight(self.symbol, self.weight)]


# ---- the look-ahead guarantee ---------------------------------------------------------------

class Cheater:
    """Tries to read tomorrow's bar, which is the one thing the engine must make impossible."""

    name = "cheater"

    def on_close(self, view, book):
        tomorrow = view.panel.sessions[view.t + 1]
        view.at(tomorrow)               # must raise
        return []


def test_a_strategy_that_reads_tomorrow_is_caught():
    panel = panel_from({"AAA": flat(10)})
    with pytest.raises(FutureDataError):
        Backtester(panel, BASE).run(Cheater())


def test_the_strategy_is_never_called_on_the_final_session():
    """Nothing can be placed for a session that does not exist."""
    calls = []

    class Recorder:
        name = "recorder"

        def on_close(self, view, book):
            calls.append(view.today)
            return []

    panel = panel_from({"AAA": flat(6)})
    Backtester(panel, BASE).run(Recorder())
    assert calls == panel.sessions[:-1]


# ---- order lifecycle -------------------------------------------------------------------------

def test_entry_fills_next_session_not_today():
    """An intent decided at the close of t can only fill on t+1."""
    bars = flat(6, 100.0)
    bars[1] = (100.0, 100.5, 98.0, 99.0, 10_000_000)      # dips to the limit on session 1
    panel = panel_from({"AAA": bars})
    intent = BracketIntent.of("AAA", entry_limit=99, take_profit=110, stop_loss=95, notional=10_000)
    result = Backtester(panel, BASE).run(Once(intent, on_session=0))
    assert result.equity["n_positions"].tolist() == [0, 1, 1, 1, 1, 1]


def test_an_unfilled_limit_expires_rather_than_resting():
    """Day time-in-force: one session, then the order is gone (Alpaca brackets need day or gtc)."""
    panel = panel_from({"AAA": flat(6, 100.0)})
    intent = BracketIntent.of("AAA", entry_limit=90, take_profit=110, stop_loss=85, notional=10_000)
    result = Backtester(panel, BASE).run(Once(intent, on_session=0))
    assert result.diagnostics["entries_expired"] == 1
    assert result.diagnostics["entries_filled"] == 0


def test_a_full_round_trip_records_the_exit_reason_and_pnl():
    bars = flat(8, 100.0)
    bars[1] = (100.0, 100.5, 98.0, 99.5, 10_000_000)      # entry fills at 99
    bars[4] = (105.0, 112.0, 104.0, 111.0, 10_000_000)    # target hit
    panel = panel_from({"AAA": bars})
    intent = BracketIntent.of("AAA", entry_limit=99, take_profit=110, stop_loss=95, notional=9_900)
    result = Backtester(panel, BASE).run(Once(intent, on_session=0))

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "take_profit"
    assert trade.entry_price == D("99.00")
    assert trade.exit_price == D("110.00")
    assert trade.qty == 100
    assert trade.gross_pnl == D("1100.00")
    assert result.final_equity == D("101100.00")


def test_the_ambiguity_rate_is_reported():
    bars = flat(8, 100.0)
    bars[1] = (100.0, 100.5, 98.0, 99.5, 10_000_000)
    bars[3] = (101.0, 112.0, 94.0, 108.0, 10_000_000)     # touched both levels
    panel = panel_from({"AAA": bars})
    intent = BracketIntent.of("AAA", entry_limit=99, take_profit=110, stop_loss=95, notional=9_900)
    result = Backtester(panel, BASE).run(Once(intent, on_session=0))
    assert result.trades[0].exit_reason == "stop_loss"
    assert result.trades[0].ambiguous_bar is True
    assert result.diagnostics["ambiguity_rate"] == 1.0


# ---- sizing caps -----------------------------------------------------------------------------

def test_fixed_fractional_sizing_risks_the_configured_fraction():
    """1% of $100k equity risked over a $5 stop is $1,000 / $5 = 200 shares."""
    bars = flat(6, 100.0)
    bars[1] = (100.0, 100.5, 99.0, 99.5, 10_000_000)
    panel = panel_from({"AAA": bars})
    intent = BracketIntent.of("AAA", entry_limit=100, take_profit=110, stop_loss=95,
                              risk_fraction="0.01")
    result = Backtester(panel, BASE).run(Once(intent, on_session=0))
    assert result.trades == [] and result.diagnostics["entries_filled"] == 1
    # 200 shares at 100 is $20,000 of notional, which the ADV cap must not have reduced here.
    assert result.equity["positions_value"].iloc[1] == D("19900.00")


def test_adv_participation_caps_the_position():
    """A thin name cannot absorb the size fixed-fractional sizing asks for."""
    thin = flat(6, 100.0, volume=1_000)                   # $100k a day of dollar volume
    thin[1] = (100.0, 100.5, 99.0, 99.5, 1_000)
    panel = panel_from({"AAA": thin})
    intent = BracketIntent.of("AAA", entry_limit=100, take_profit=110, stop_loss=95,
                              risk_fraction="0.01")
    config = BacktestConfig(initial_cash=D("100000.00"), costs=ZERO_COSTS, tax=NO_TAX,
                            apply_dividends=False, liquidate_at_end=False,
                            adv_participation=D("0.01"))
    result = Backtester(panel, config).run(Once(intent, on_session=0))
    assert result.diagnostics["adv_capped"] == 1
    # 1% of $100,000 ADV is $1,000, which buys 10 shares at 100.
    assert result.equity["positions_value"].iloc[1] == D("995.00")


# ---- tax interaction -------------------------------------------------------------------------

def test_the_blacklist_blocks_a_re_entry_after_a_loss():
    """A loss sale blacklists the symbol for 31 days, and the engine must refuse to re-enter."""
    # 20 sessions ends 2026-01-30, before the 2026-02-08 expiry: the ledger drops an entry once
    # the cooldown lapses, so a longer run would (correctly) show an empty blacklist at the end.
    bars = flat(20, 100.0)
    bars[1] = (100.0, 100.5, 98.0, 99.5, 10_000_000)      # entry
    bars[3] = (100.0, 100.5, 94.0, 96.0, 10_000_000)      # stop
    panel = panel_from({"AAA": bars})
    intent = BracketIntent.of("AAA", entry_limit=99, take_profit=110, stop_loss=95, notional=9_900)

    class Always:
        name = "always"

        def on_close(self, view, book):
            return [intent]

    config = BacktestConfig(initial_cash=D("100000.00"), costs=ZERO_COSTS, tax=TaxConfig(
        short_term_rate=D("0.32"), payment_schedule="none"), apply_dividends=False,
        liquidate_at_end=False)
    result = Backtester(panel, config).run(Always())
    assert result.diagnostics["blacklist_blocked"] > 0
    assert result.ledger.is_blacklisted("AAA", panel.sessions[10])


def test_the_tax_reserve_is_withheld_from_sizable_cash():
    """The reserve is real money that must not be traded (lesson 02 §7)."""
    seen = {}

    bars = flat(10, 100.0)
    bars[1] = (100.0, 100.5, 98.0, 99.5, 10_000_000)
    bars[3] = (105.0, 112.0, 104.0, 111.0, 10_000_000)    # a winner, so tax accrues
    panel = panel_from({"AAA": bars})
    intent = BracketIntent.of("AAA", entry_limit=99, take_profit=110, stop_loss=95, notional=9_900)

    class Watcher:
        name = "watcher"

        def __init__(self):
            self._seen = 0

        def on_close(self, view, book):
            self._seen += 1
            seen[view.today] = (book.cash, book.sizable_cash)
            return [intent] if self._seen == 1 else []

    config = BacktestConfig(initial_cash=D("100000.00"), costs=ZERO_COSTS, tax=TaxConfig(
        short_term_rate=D("0.32"), payment_schedule="none"), apply_dividends=False,
        liquidate_at_end=False)
    result = Backtester(panel, config).run(Watcher())

    after_exit = panel.sessions[4]
    cash, sizable = seen[after_exit]
    assert result.equity["reserve"].loc[after_exit] == D("352.00")     # 32% of the $1,100 gain
    assert cash - sizable == D("352.00")


def test_dividends_are_credited_and_taxed_as_ordinary_when_held_briefly():
    """A swing bot rarely holds 61 days, so its dividends are ordinary income, not qualified."""
    days = sessions(8)
    factors = [0.99, 0.99, 0.99, 1.0, 1.0, 1.0, 1.0, 1.0]
    rows = [{"trade_date": d, "symbol": "AAA", "open": 100.0, "high": 100.5, "low": 99.5,
             "close": 100.0, "volume": 10_000_000, "adj_factor": f, "segment_id": 0}
            for d, f in zip(days, factors, strict=True)]
    panel = Panel.from_frame(pd.DataFrame(rows), days)
    config = BacktestConfig(initial_cash=D("100000.00"), costs=ZERO_COSTS, apply_dividends=True,
                            liquidate_at_end=False, allow_fractional=False,
                            tax=TaxConfig(short_term_rate=D("0.32"),
                                          qualified_dividend_rate=D("0.15"),
                                          payment_schedule="none"))
    result = Backtester(panel, config).run(HoldWeight("AAA", D("0.5")))
    assert result.diagnostics["dividends"] == 1
    assert result.ledger.dividends_received > 0
    # Ordinary rate (0.32), not the qualified rate (0.15).
    expected = (result.ledger.dividends_received * D("0.32")).quantize(D("0.01"))
    assert result.equity["reserve"].iloc[-1] == expected


def test_liquidation_at_the_end_pays_the_deferred_tax_bill():
    """Buy and hold pays nothing year to year; the post-liquidation value is where it settles up."""
    bars = [(100.0 + i, 101.0 + i, 99.0 + i, 100.0 + i, 10_000_000) for i in range(10)]
    panel = panel_from({"AAA": bars})
    config = BacktestConfig(initial_cash=D("100000.00"), costs=ZERO_COSTS, apply_dividends=False,
                            liquidate_at_end=True,
                            tax=TaxConfig(short_term_rate=D("0.32"), payment_schedule="none"))
    result = Backtester(panel, config).run(HoldWeight())
    assert result.equity["reserve"].iloc[-1] == D("0.00")         # nothing realized while holding
    assert result.terminal["liquidated"] is True
    assert result.terminal["terminal_tax"] > 0
    assert result.post_liquidation_value < result.final_equity


def test_the_config_fingerprint_changes_with_the_config():
    """Phase 4 counts parameter trials by this hash, so it must be sensitive and stable."""
    a = BacktestConfig(entry_buffer=D("0.01"))
    b = BacktestConfig(entry_buffer=D("0.05"))
    assert a.fingerprint() == BacktestConfig(entry_buffer=D("0.01")).fingerprint()
    assert a.fingerprint() != b.fingerprint()


def test_costs_reduce_the_result_relative_to_a_frictionless_run():
    bars = flat(8, 100.0)
    bars[1] = (100.0, 100.5, 98.0, 99.5, 10_000_000)
    bars[4] = (105.0, 112.0, 104.0, 111.0, 10_000_000)
    panel = panel_from({"AAA": bars})
    intent = BracketIntent.of("AAA", entry_limit=99, take_profit=110, stop_loss=95, notional=9_900)
    free = Backtester(panel, BASE).run(Once(intent, on_session=0))
    costed = Backtester(panel, BacktestConfig(
        initial_cash=D("100000.00"), costs=CostModel(), tax=NO_TAX, apply_dividends=False,
        liquidate_at_end=False)).run(Once(intent, on_session=0))
    assert costed.final_equity < free.final_equity
    assert costed.trades[0].fees > 0


# ---- Phase 3: securities that stop trading, strict fills, R ----------------------------------

def panel_with_gaps(series: dict[str, list[tuple | None]], segments: dict[str, list[int]] | None
                    = None) -> Panel:
    """Like `panel_from`, but a None bar is a session with no print, and segments can change."""
    n = max(len(v) for v in series.values())
    days = sessions(n)
    rows = []
    for symbol, path in series.items():
        for i, bar in enumerate(path):
            if bar is None:
                continue
            o, h, l, c, v = bar
            seg = (segments or {}).get(symbol, [0] * n)[i]
            rows.append({"trade_date": days[i], "symbol": symbol, "open": o, "high": h, "low": l,
                         "close": c, "volume": v, "adj_factor": 1.0, "segment_id": seg})
    return Panel.from_frame(pd.DataFrame(rows), days)


def test_an_acquired_position_is_cashed_out_at_its_last_mark_not_held_forever():
    """Lesson 03: the zombie-position defect. No more bars must not mean 'hold until the end'."""
    path = flat(5, 100.0) + [(101.0, 102.0, 100.5, 101.5, 10_000_000)] + [None] * 10
    panel = panel_with_gaps({"AAA": path, "SPY": flat(16, 300.0)})
    intent = BracketIntent.of("AAA", entry_limit=100.5, take_profit=110, stop_loss=95,
                              notional=10_050)
    result = Backtester(panel, BASE).run(Once(intent, on_session=0))

    trade = result.trades[0]
    assert trade.exit_reason == "delisted"
    assert trade.exit_price == D("101.50")                  # the last close it ever printed
    assert trade.exit_date == panel.sessions[5 + BASE.delist_after_missing]
    assert result.diagnostics["delisted_exits"] == 1
    assert result.equity["n_positions"].iloc[-1] == 0


def test_a_reused_ticker_never_marks_or_stops_out_the_old_company():
    """The DCT case: a new company under the same ticker trades below the old stop."""
    n = 40
    path = flat(5, 100.0) + [None] * 25 + [(50.0, 51.0, 49.0, 50.0, 10_000_000)] * 10
    segments = {"AAA": [0] * 30 + [1] * 10}
    panel = panel_with_gaps({"AAA": path, "SPY": flat(n, 300.0)}, segments)
    intent = BracketIntent.of("AAA", entry_limit=100.5, take_profit=110, stop_loss=95,
                              notional=10_050)
    result = Backtester(panel, BASE).run(Once(intent, on_session=0))
    trade = result.trades[0]
    assert trade.exit_reason == "delisted" and trade.exit_price == D("100.00")


def test_a_short_halt_lets_the_bracket_rest_and_resume():
    path = flat(4, 100.0) + [None] * 3 + [(105.0, 111.0, 104.0, 110.0, 10_000_000)] + flat(3, 110.0)
    panel = panel_with_gaps({"AAA": path, "SPY": flat(11, 300.0)})
    intent = BracketIntent.of("AAA", entry_limit=100.5, take_profit=110, stop_loss=95,
                              notional=10_050)
    result = Backtester(panel, BASE).run(Once(intent, on_session=0))
    assert result.trades[0].exit_reason == "take_profit"


def test_strict_fills_reject_an_entry_the_bar_only_touched():
    bars = flat(6, 100.0)
    bars[1] = (100.0, 100.5, 99.0, 99.5, 10_000_000)        # low exactly at the 99 limit
    panel = panel_from({"AAA": bars})
    intent = BracketIntent.of("AAA", entry_limit=99, take_profit=110, stop_loss=95, notional=9_900)
    loose = Backtester(panel, BASE).run(Once(intent, on_session=0))
    strict = Backtester(panel, BacktestConfig(**{**BASE.__dict__, "strict_fills": True})).run(
        Once(intent, on_session=0))
    assert loose.diagnostics["touch_fills"] == 1
    assert strict.diagnostics["entries_filled"] == 0 and strict.diagnostics["strict_rejected"] == 1


def test_each_bracketed_trade_records_its_r_multiple():
    bars = flat(8, 100.0)
    bars[1] = (100.0, 100.5, 98.0, 99.5, 10_000_000)        # fills at 99: R = 99 - 95 = 4
    bars[4] = (105.0, 112.0, 104.0, 111.0, 10_000_000)      # target 110: +11 = +2.75R
    panel = panel_from({"AAA": bars})
    intent = BracketIntent.of("AAA", entry_limit=99, take_profit=110, stop_loss=95, notional=9_900)
    trade = Backtester(panel, BASE).run(Once(intent, on_session=0)).trades[0]
    assert trade.risk_per_share == D("4.00")
    assert trade.r_multiple == pytest.approx(2.75)


def test_a_gap_in_our_own_data_is_not_a_delisting():
    """The store running behind the calendar leaves every symbol blank; that says nothing about
    any one company, so the position must reach the end and be liquidated normally."""
    path = flat(6, 100.0) + [None] * 10
    panel = panel_with_gaps({"AAA": path, "SPY": flat(6, 300.0) + [None] * 10})
    intent = BracketIntent.of("AAA", entry_limit=100.5, take_profit=110, stop_loss=95,
                              notional=10_050)
    config = BacktestConfig(**{**BASE.__dict__, "liquidate_at_end": True})
    result = Backtester(panel, config).run(Once(intent, on_session=0))
    assert result.diagnostics["delisted_exits"] == 0
    assert result.trades[0].exit_reason == "terminal_liquidation"
