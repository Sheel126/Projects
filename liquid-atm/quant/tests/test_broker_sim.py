"""The intrabar and limit-entry rules (lesson 02 §2-§3).

These are pure functions on one bar, which is the point: the two assumptions that decide whether a
daily-bar backtest is honest get tested directly instead of being inferred from an equity curve.
"""

from decimal import Decimal

import pytest

from liquid_atm_quant.backtest.broker_sim import Bar, entry_fill, exit_fill
from liquid_atm_quant.backtest.costs import ZERO_COSTS, CostModel

D = Decimal
TARGET, STOP = D("110.00"), D("95.00")
COSTS = CostModel()


def resolve(bar, days_held=0, time_stop=None, costs=ZERO_COSTS):
    return exit_fill(bar, TARGET, STOP, days_held, time_stop, costs)


# ---- exits ---------------------------------------------------------------------------------

def test_ambiguous_bar_resolves_as_a_stop():
    """The bar touched 111 and 94: unknowable order, so the stop wins and it is flagged."""
    fill = resolve(Bar(open=101, high=111, low=94, close=108))
    assert fill.reason == "stop_loss"
    assert fill.ambiguous is True
    assert fill.kind == "ambiguous_stop"
    assert fill.price == STOP          # ZERO_COSTS: no slippage to subtract


def test_gap_below_the_stop_fills_at_the_open_not_at_the_stop():
    """A stop at 95 on a bar that opens at 91 fills at 91. Anything else invents liquidity."""
    fill = resolve(Bar(open=91, high=93, low=88, close=90))
    assert fill.kind == "gap_stop"
    assert fill.price == D("91.00")
    assert fill.ambiguous is False


def test_gap_above_the_target_fills_at_the_open():
    fill = resolve(Bar(open=115, high=118, low=114, close=117))
    assert (fill.kind, fill.reason, fill.price) == ("gap_target", "take_profit", D("115.00"))


def test_gap_is_checked_before_the_ambiguity_rule():
    """Opens below the stop AND reaches the target later: the open came first, so it is a stop."""
    fill = resolve(Bar(open=94, high=112, low=93, close=111))
    assert fill.kind == "gap_stop"
    assert fill.price == D("94.00")
    assert fill.ambiguous is False


def test_clean_target_fills_at_the_limit_with_no_slippage():
    fill = resolve(Bar(open=101, high=112, low=100, close=111), costs=COSTS)
    assert (fill.reason, fill.price) == ("take_profit", TARGET)


def test_triggered_stop_pays_slippage_because_it_becomes_a_market_order():
    fill = resolve(Bar(open=101, high=102, low=94, close=96), costs=COSTS)
    assert fill.reason == "stop_loss"
    assert fill.price < STOP
    assert fill.price == STOP - COSTS.stop_slippage(STOP)


def test_slippage_is_at_least_one_tick():
    cheap = CostModel(slippage_bps=D("0"))
    assert cheap.stop_slippage(D("95.00")) == D("0.01")


def test_no_trigger_returns_none():
    assert resolve(Bar(open=101, high=105, low=99, close=103)) is None


def test_time_stop_exits_at_the_close_only_once_the_horizon_is_reached():
    quiet = Bar(open=101, high=105, low=99, close=103)
    assert resolve(quiet, days_held=9, time_stop=10) is None
    fill = resolve(quiet, days_held=10, time_stop=10)
    assert (fill.reason, fill.price) == ("time_stop", D("103.00"))


def test_a_triggered_level_beats_the_time_stop_on_the_same_bar():
    fill = resolve(Bar(open=101, high=112, low=100, close=111), days_held=99, time_stop=10)
    assert fill.reason == "take_profit"


# ---- entries -------------------------------------------------------------------------------

LIMIT = D("100.00")


def test_limit_not_reached_does_not_fill():
    assert entry_fill(Bar(open=104, high=106, low=101, close=105), LIMIT) is None


def test_gap_below_the_limit_fills_at_the_open_which_is_better_than_asked():
    fill = entry_fill(Bar(open=98, high=101, low=97, close=100), LIMIT)
    assert (fill.price, fill.touched_only) == (D("98.00"), False)


def test_trading_through_the_limit_is_a_clean_fill():
    fill = entry_fill(Bar(open=103, high=104, low=99.50, close=102), LIMIT)
    assert (fill.price, fill.touched_only) == (LIMIT, False)


def test_a_bar_that_only_touches_the_limit_fills_but_is_flagged():
    """These are the fills where a daily-bar backtest is most likely lying (lesson 02 §3)."""
    fill = entry_fill(Bar(open=103, high=104, low=100.00, close=103), LIMIT)
    assert (fill.price, fill.touched_only) == (LIMIT, True)


def test_strict_buffer_rejects_a_touch():
    """Phase 4's strict mode: require real depth through the limit, not a graze."""
    bar = Bar(open=103, high=104, low=99.99, close=103)
    assert entry_fill(bar, LIMIT, buffer=D("0.01")).touched_only is False
    assert entry_fill(bar, LIMIT, buffer=D("0.50")).touched_only is True


@pytest.mark.parametrize("bar", [
    Bar(open=101, high=111, low=94, close=108),      # both touched
    Bar(open=91, high=93, low=88, close=90),         # gapped through the stop
])
def test_every_ambiguous_or_gapped_bar_resolves_to_a_loss_never_a_win(bar):
    """The pessimism is unconditional: no bar shape may turn an unknowable path into a winner."""
    assert resolve(bar).reason == "stop_loss"
