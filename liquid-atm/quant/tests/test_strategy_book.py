"""Portfolio construction (lesson 03 §6): sizing, then each of the four limits binding in turn."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from liquid_atm_quant.backtest.strategy import PortfolioSnapshot
from liquid_atm_quant.strategy.book import build, open_heat
from liquid_atm_quant.strategy.params import FunnelParams
from liquid_atm_quant.strategy.regime import Regime
from liquid_atm_quant.strategy.screener import Candidate

D = Decimal
P = FunnelParams()


def cand(symbol, entry="100.00", stop="96.00", sector="Industrials"):
    entry, stop = D(entry), D(stop)
    return Candidate(symbol, sector, 1.0, 2.0, entry, (entry - stop) / 2, entry, stop,
                     entry + (entry - stop) * D("1.5"))


def snapshot(equity="100000.00", positions=None, stops=None):
    return PortfolioSnapshot(date(2024, 1, 2), D(equity), D(equity), D(equity),
                             positions or {}, frozenset(), stops or {})


def test_fixed_fractional_sizing_risks_three_quarters_of_a_percent():
    """$750 of risk over a $4 stop is 187.5 shares, i.e. $18,750 - over the 15% cap, so $15,000."""
    out = build([cand("A")], snapshot(), Regime.RISK_ON, {}, {}, P)
    intent = out.intents[0]
    assert intent.notional == D("15000.00")
    assert intent.time_stop_days == 10 and intent.regime == "risk_on"
    # Below the cap, the risk formula sets the size: a $10 stop -> 75 shares -> $7,500.
    wide = build([cand("B", stop="90.00")], snapshot(), Regime.RISK_ON, {}, {}, P)
    assert wide.intents[0].notional == D("7500.00")


def test_caution_halves_the_risk_and_allows_one_entry():
    many = [cand(s, stop="90.00", sector=s) for s in "ABC"]
    out = build(many, snapshot(), Regime.CAUTION, {}, {}, P)
    assert [i.symbol for i in out.intents] == ["A"]
    assert out.intents[0].notional == D("3750.00")
    assert out.skipped["pacing"] == 2


def test_risk_off_places_nothing():
    assert build([cand("A")], snapshot(), Regime.RISK_OFF, {}, {}, P).intents == []


def test_pacing_limits_new_entries_to_three_a_day():
    many = [cand(s, stop="90.00", sector=s) for s in "ABCDE"]
    out = build(many, snapshot(), Regime.RISK_ON, {}, {}, P)
    assert [i.symbol for i in out.intents] == ["A", "B", "C"]
    assert out.skipped["pacing"] == 2


def test_the_sector_cap_counts_what_is_already_held():
    held = {"H1": D(10), "H2": D(10)}
    sectors = {"H1": "Energy", "H2": "Energy"}
    out = build([cand("A", sector="Energy", stop="90.00"), cand("B", sector="Energy", stop="90.00"),
                 cand("C", sector="Utilities", stop="90.00")],
                snapshot(positions=held), Regime.RISK_ON, {}, sectors, P)
    assert [i.symbol for i in out.intents] == ["A", "C"]
    assert out.skipped["sector"] == 1


def test_heat_is_measured_from_todays_close_to_each_stop():
    book = snapshot(positions={"H": D(100)}, stops={"H": D("90.00")})
    assert open_heat(book, {"H": 120.0}) == D("3000.00")     # a winner carries more heat
    assert open_heat(book, {"H": 85.0}) == D("0")             # already through its stop


def test_the_heat_cap_stops_new_risk_once_six_percent_is_open():
    # $5,500 already at risk; a new $750 trade would take it to $6,250 > $6,000.
    book = snapshot(positions={"H": D(550)}, stops={"H": D("90.00")})
    out = build([cand("A", stop="90.00")], book, Regime.RISK_ON, {"H": 100.0}, {}, P)
    assert out.intents == [] and out.skipped["heat"] == 1
    assert out.heat_before == D("5500.00")


def test_no_slots_no_entries():
    held = {f"H{i}": D(1) for i in range(10)}
    out = build([cand("A")], snapshot(positions=held), Regime.RISK_ON, {}, {}, P)
    assert out.intents == [] and out.skipped["slots"] == 1


def test_an_order_below_the_minimum_notional_is_dropped():
    out = build([cand("A", stop="90.00")], snapshot(equity="1000.00"), Regime.RISK_ON, {}, {},
                replace(P, risk_per_trade=0.001))
    assert out.intents == [] and out.skipped["too_small"] == 1
