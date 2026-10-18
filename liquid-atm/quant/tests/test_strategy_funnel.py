"""The funnel end to end (lesson 03), the trial hash, and the lockbox guard (§1)."""

from datetime import date
from decimal import Decimal

import pytest

from liquid_atm_quant.backtest.costs import ZERO_COSTS
from liquid_atm_quant.backtest.engine import BacktestConfig, Backtester, run_hash
from liquid_atm_quant.backtest.strategy import PortfolioSnapshot
from liquid_atm_quant.baselines import BuyAndHold
from liquid_atm_quant.strategy import (LOCKBOX_START, FunnelParams, LockboxError, MomentumFunnel,
                                       assert_outside_lockbox)
from liquid_atm_quant.tax.ledger import TaxConfig

import synth

D = Decimal
AT = 270                                      # the breakout session
FILLERS = {f"F{i}": synth.bars(synth.trend(synth.N, 40.0 + i, 0.002)) for i in range(3)}


def funnel_panel(spy_daily=0.0005):
    series = {"SPY": synth.spy(daily=spy_daily),
              "WIN": synth.bars(synth.breakout(at=AT), spikes={AT: 3.0}), **FILLERS}
    return synth.panel(series, members={"WIN", *FILLERS})


def empty_book(panel, t):
    return PortfolioSnapshot(panel.sessions[t], D("100000.00"), D("100000.00"), D("100000.00"),
                             {}, frozenset())


def test_a_planted_breakout_produces_exactly_one_bracket_at_the_right_levels():
    panel = funnel_panel()
    funnel = MomentumFunnel(FunnelParams(include_sector_etfs=False))
    decision = funnel.decide(panel.view(AT), empty_book(panel, AT))

    assert decision.regime.state.value == "risk_on"
    assert [i.symbol for i in decision.intents] == ["WIN"]
    intent, c = decision.intents[0], decision.screen.candidates[0]
    assert (intent.entry_limit, intent.stop_loss, intent.take_profit) == \
        (c.entry_limit, c.stop_loss, c.take_profit)
    assert intent.time_stop_days == 10


def test_nothing_is_placed_the_day_before_the_breakout():
    panel = funnel_panel()
    funnel = MomentumFunnel(FunnelParams(include_sector_etfs=False))
    assert funnel.decide(panel.view(AT - 1), empty_book(panel, AT - 1)).intents == []


def test_risk_off_finds_the_candidate_but_places_nothing():
    panel = funnel_panel(spy_daily=-0.001)
    funnel = MomentumFunnel(FunnelParams(include_sector_etfs=False))
    decision = funnel.decide(panel.view(AT), empty_book(panel, AT))
    assert decision.regime.state.value == "risk_off"
    assert [c.symbol for c in decision.screen.candidates] == ["WIN"]
    assert decision.intents == []


def test_the_veto_hook_removes_a_candidate_before_the_book():
    panel = funnel_panel()
    funnel = MomentumFunnel(FunnelParams(include_sector_etfs=False),
                            veto=lambda c, day: "pump" if c.symbol == "WIN" else None)
    decision = funnel.decide(panel.view(AT), empty_book(panel, AT))
    assert decision.vetoed == {"WIN": "pump"} and decision.intents == []


def test_through_the_engine_the_breakout_becomes_one_trade_with_an_r_multiple():
    panel = funnel_panel()
    config = BacktestConfig(costs=ZERO_COSTS, apply_dividends=False,
                            tax=TaxConfig(payment_schedule="none"))
    result = Backtester(panel, config).run(MomentumFunnel(FunnelParams(include_sector_etfs=False)))

    assert [t.symbol for t in result.trades] == ["WIN"]
    trade = result.trades[0]
    assert trade.entry_date == panel.sessions[AT + 1]       # decided at the close, filled next day
    assert trade.r_multiple is not None and trade.risk_per_share > 0
    funnel_diag = result.diagnostics["strategy"]
    assert funnel_diag["intents"] == 1
    assert sum(funnel_diag["regime_days"].values()) == len(panel.sessions) - 1


# ---- trials and the lockbox ------------------------------------------------------------------

def test_every_parameter_change_is_a_new_trial():
    config = BacktestConfig()
    base = run_hash(config, MomentumFunnel())
    assert run_hash(config, MomentumFunnel()) == base
    assert run_hash(config, MomentumFunnel(FunnelParams(stop_atr=2.5))) != base
    # A strategy with no parameters keeps the Phase 2 hash, so stored baseline runs stay valid.
    assert run_hash(config, BuyAndHold("SPY")) == config.fingerprint()


def test_command_line_overrides_are_cast_to_the_field_type():
    p = FunnelParams().with_overrides({"stop_atr": "2.5", "time_stop_days": "7",
                                       "include_sector_etfs": "false"})
    assert (p.stop_atr, p.time_stop_days, p.include_sector_etfs) == (2.5, 7, False)
    with pytest.raises(KeyError):
        FunnelParams().with_overrides({"stopp_atr": "2"})


def test_the_lockbox_refuses_a_run_that_reaches_into_the_holdout():
    assert_outside_lockbox(date(2024, 9, 30))
    with pytest.raises(LockboxError):
        assert_outside_lockbox(LOCKBOX_START)
    assert_outside_lockbox(date(2026, 9, 18), unlock=True)
