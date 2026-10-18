"""The five screener filters (lesson 03 §3) and the bracket levels (§4-§5).

One synthetic name per filter, each built to fail exactly that filter, plus one that passes all
five. If a filter is broken, the wrong name gets through or the right one does not.
"""

from dataclasses import replace
from decimal import Decimal

import pytest

from liquid_atm_quant.strategy.indicators import Indicators
from liquid_atm_quant.strategy.params import FunnelParams
from liquid_atm_quant.strategy.screener import Screener, bracket

import synth

D = Decimal
LAST = synth.N - 1
SPIKE = {LAST: 3.0}


def extended():
    """Consolidation, then six +2.5% days: a fresh high, but far above its 20-day average."""
    closes = synth.breakout(jump=0.0)
    closes[-6:] = closes[-7] * 1.025 ** synth.np.arange(1, 7)
    return closes


UNIVERSE = {
    "WIN": synth.bars(synth.breakout(), spikes=SPIKE),
    "CHEAP": synth.bars(synth.breakout() * 0.03, volume=100_000_000, spikes=SPIKE),  # ~$4.50
    "THIN": synth.bars(synth.breakout(), volume=10_000, spikes=SPIKE),              # ~$1.5M ADV
    "DOWN": synth.bars(synth.trend(synth.N, 200.0, -0.002), spikes=SPIKE),
    "QUIET": synth.bars(synth.breakout(), spikes=None),                             # no volume
    "EXT": synth.bars(extended(), spikes=SPIKE),
}
MEMBERS = set(UNIVERSE)
ALL_THROUGH_MOMENTUM = FunnelParams(momentum_top=1.0, include_sector_etfs=False)


def screener(params=ALL_THROUGH_MOMENTUM, universe=None, sectors=None):
    universe = universe or UNIVERSE
    panel = synth.panel({"SPY": synth.spy(), **universe}, members=set(universe))
    ind = Indicators.compute(panel, params)
    return Screener(ind, panel.symbols, panel.member, params, sectors or {})


def test_each_filter_removes_exactly_the_name_built_to_fail_it():
    result = screener().screen(LAST)
    assert [c.symbol for c in result.candidates] == ["WIN"]
    assert result.counts == {"universe": 6, "eligible": 4,   # CHEAP, THIN out
                             "trend": 3,                     # DOWN out
                             "momentum": 3,                  # top 100% here
                             "trigger": 2,                   # QUIET out
                             "extension": 1}                 # EXT out


def test_momentum_keeps_only_the_top_fraction_of_what_is_in_trend():
    strong = synth.bars(synth.breakout(daily=0.006, start=20.0), spikes=SPIKE)
    weak = synth.bars(synth.breakout(daily=0.002, start=100.0), spikes=SPIKE)
    params = FunnelParams(momentum_top=0.5, include_sector_etfs=False)
    result = screener(params, {"STRONG": strong, "WEAK": weak}).screen(LAST)
    assert result.counts["momentum"] == 1
    assert [c.symbol for c in result.candidates] == ["STRONG"]


def test_held_and_blacklisted_names_are_excluded_before_they_use_a_slot():
    result = screener().screen(LAST, exclude={"WIN"})
    assert result.candidates == []
    assert result.counts["eligible"] == 3


def test_a_candidate_carries_its_sector_and_unknown_is_the_default():
    found = screener(sectors={"WIN": "Industrials"}).screen(LAST).candidates
    assert found[0].sector == "Industrials"
    assert screener().screen(LAST).candidates[0].sector == "Unknown"


def test_the_candidate_bracket_is_built_from_the_close_and_raw_atr():
    c = screener().screen(LAST).candidates[0]
    atr = float(c.atr)
    assert float(c.entry_limit) == pytest.approx(float(c.close) + 0.25 * atr, abs=0.011)
    assert float(c.entry_limit - c.stop_loss) == pytest.approx(2 * atr, abs=0.011)
    assert float(c.take_profit - c.entry_limit) == pytest.approx(3 * atr, abs=0.011)


def test_bracket_levels_and_rounding_never_tighten_the_bracket():
    p = FunnelParams()
    assert bracket(100.0, 2.0, p) == (D("100.50"), D("96.50"), D("106.50"))
    entry, stop, target = bracket(100.0, 1.2345, p)
    assert entry == D("100.31")                     # 100.308625 rounded
    assert stop == D("97.84")                       # 97.841 rounded down, never up
    assert target == D("104.02")                    # 104.0135 rounded up, never down


def test_a_bracket_whose_stop_would_be_at_or_below_zero_is_dropped():
    assert bracket(1.0, 1.0, replace(FunnelParams(), stop_atr=2.0)) is None
