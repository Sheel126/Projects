"""Phase 3d (lesson 03d): intraday strategies, copying insiders and funds, and the split fix."""

import io
import zipfile
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from liquid_atm_quant.backtest.engine import BacktestConfig, Backtester
from liquid_atm_quant.backtest.panel import Panel
from liquid_atm_quant.baselines import BuyAndHold
from liquid_atm_quant.data import form13f, insiders
from liquid_atm_quant.intraday import fvg, orb
from liquid_atm_quant.intraday.account import DailyBar, DayOutcome, run_account
from liquid_atm_quant.intraday.bars import NY
from liquid_atm_quant.intraday.noise_band import NoiseBand, NoiseBandParams, SessionGrid
from liquid_atm_quant.investors.clone13f import (Clone13F, Filing, previous_quarter_end,
                                                 quarter_ends)
from liquid_atm_quant.investors.insiders import InsiderParams, clusters, routine_owners
from liquid_atm_quant.tax.ledger import TaxLedger
from synth import sessions as synth_sessions

D = Decimal


# ---- minute-bar helpers -------------------------------------------------------------------

def day_frame(day: date, closes: np.ndarray, volume: float = 1_000.0,
              spread: float = 0.02) -> pd.DataFrame:
    """One session of 1-minute bars: open = previous close, high/low a little outside."""
    stamps = [datetime.combine(day, time(9, 30), NY) + timedelta(minutes=i)
              for i in range(len(closes))]
    opens = np.r_[closes[0], closes[:-1]]
    return pd.DataFrame({"o": opens, "h": np.maximum(opens, closes) + spread,
                         "l": np.minimum(opens, closes) - spread, "c": closes,
                         "v": volume, "vw": (opens + closes) / 2},
                        index=pd.DatetimeIndex(stamps, name="t"))


def wiggle_day(day: date, base: float, amp: float = 0.002) -> pd.DataFrame:
    """A noisy day that ends where it started: no trend for the noise band to follow."""
    k = np.arange(390)
    return day_frame(day, base * (1 + amp * np.sin(k / 7.0)))


def trend_day(day: date, base: float, total: float) -> pd.DataFrame:
    return day_frame(day, base * (1 + total * np.linspace(0, 1, 390)))


def minutes(days: list[pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(days)


# ---- the noise band -----------------------------------------------------------------------

def test_noise_band_goes_long_on_a_trend_day_after_quiet_ones():
    days = synth_sessions(20)
    frames = [wiggle_day(d, 100.0 + (i % 3) * 0.3) for i, d in enumerate(days[:-1])]
    frames.append(trend_day(days[-1], 100.0, 0.03))
    grid = SessionGrid(minutes(frames))
    nb = NoiseBand(grid, NoiseBandParams(commission_per_share=0, slippage_per_share=0))
    out = nb.day(days[-1], 100_000.0)
    assert out.trades == 1 and out.pnl > 0


def test_noise_band_day_is_unchanged_by_the_future():
    """Truncation invariance: removing every later session cannot change day t's trades."""
    days = synth_sessions(30)
    rng = np.random.default_rng(3)
    frames = []
    for i, d in enumerate(days):
        frames.append(trend_day(d, 100.0, float(rng.normal(0, 0.01))) if i % 4 == 0
                      else wiggle_day(d, 100.0))
    full = NoiseBand(SessionGrid(minutes(frames)))
    for cut in (20, 24):
        short = NoiseBand(SessionGrid(minutes(frames[:cut + 1])))
        a, b = full.day(days[cut], 50_000.0), short.day(days[cut], 50_000.0)
        assert (a.pnl, a.trades) == (b.pnl, b.trades)


def test_noise_band_sizes_by_yesterdays_volatility_and_caps_leverage():
    days = synth_sessions(20)
    calm = [wiggle_day(d, 100.0 + 0.05 * (i % 2)) for i, d in enumerate(days)]
    # Daily moves of 0.05%: 2% / vol is about 40x, so the 4x cap binds.
    assert NoiseBand(SessionGrid(minutes(calm))).leverage(len(days) - 1) == pytest.approx(4.0)
    wild = [wiggle_day(d, 100.0 * (1.04 if i % 2 else 1.0)) for i, d in enumerate(days)]
    lev = NoiseBand(SessionGrid(minutes(wild))).leverage(len(days) - 1)
    assert 0.4 < lev < 0.6                       # ~4% daily vol -> about half the capital


def test_session_grid_leaves_minutes_after_an_early_close_empty():
    d = synth_sessions(1)[0]
    grid = SessionGrid(day_frame(d, np.full(210, 50.0)))
    assert grid.last[0] == 209 and np.isnan(grid.close[0, 300]) and grid.day_close[0] == 50.0


# ---- the account --------------------------------------------------------------------------

def test_account_taxes_intraday_profit_short_term_and_pays_it():
    days = synth_sessions(300)
    daily = {d: DailyBar(100.0, 100.0) for d in days}
    result = run_account(days, daily, lambda d, cap: DayOutcome(100.0, 1), "flat_100")
    years = result.diagnostics["years"]
    first = min(years)
    assert years[first]["tax"] == pytest.approx(years[first]["short_term_net"] * 0.32, abs=0.01)
    gross = 100.0 * len(days)
    assert result.post_liquidation_value == pytest.approx(100_000 + gross * 0.68, abs=1.0)


def test_account_core_is_buy_and_hold_with_long_term_tax_at_the_end():
    days = synth_sessions(400)
    prices = np.linspace(100, 150, len(days))
    daily = {d: DailyBar(float(p), float(p)) for d, p in zip(days, prices)}
    result = run_account(days, daily, None, "core", core=True)
    shares = int(100_000 / 100)
    gain = shares * (150 - 100)
    fees = 150 * shares * 27.8 / 1e6 + min(shares * 0.000166, 8.30)
    expected = 100_000 + gain - fees - (gain - fees) * 0.15
    assert result.post_liquidation_value == pytest.approx(expected, abs=2.0)


# ---- opening-range breakout -------------------------------------------------------------

def _orb_bars(day: date, path: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    stamps = [datetime.combine(day, time(9, 35), NY) + timedelta(minutes=i)
              for i in range(len(path))]
    return pd.DataFrame(path, columns=["o", "h", "l", "c"],
                        index=pd.DatetimeIndex(stamps)).assign(v=1000.0, vw=0.0)


def test_orb_long_triggers_at_the_range_high_and_holds_to_the_close():
    day = synth_sessions(1)[0]
    c = orb.Candidate("X", 1, level=10.00, atr=1.0, relative_volume=3.0)
    bars = _orb_bars(day, [(9.95, 9.99, 9.90, 9.98), (9.98, 10.10, 9.97, 10.08),
                           (10.08, 10.30, 10.05, 10.25), (10.25, 10.50, 10.20, 10.40)])
    stats = orb.OrbStats()
    p = orb.OrbParams()
    pnl = orb.trade_one(bars, c, 100, p, stats)
    entry = 10.00 + 0.01
    assert stats.triggered == 1 and stats.closed == 1
    assert pnl == pytest.approx(100 * (10.40 - entry) - 2 * 100 * p.commission_per_share)


def test_orb_entry_bar_that_also_reaches_the_stop_is_stopped():
    day = synth_sessions(1)[0]
    c = orb.Candidate("X", 1, level=10.00, atr=1.0, relative_volume=3.0)
    # The trigger bar's low reaches below entry - 0.1 ATR: pessimism says stopped, same bar.
    bars = _orb_bars(day, [(9.98, 10.05, 9.85, 10.00), (10.00, 10.60, 10.00, 10.50)])
    stats = orb.OrbStats()
    pnl = orb.trade_one(bars, c, 100, orb.OrbParams(), stats)
    assert stats.stopped == 1 and stats.ambiguous == 1 and pnl < 0


def test_orb_selection_uses_relative_volume_from_previous_sessions_only():
    days = synth_sessions(20)
    rows = []
    for i, d in enumerate(days):
        rows.append((d, "HOT", 20.0, 20.5, 19.9, 20.4, 5_000_000 if i == 19 else 100_000))
        rows.append((d, "COLD", 30.0, 30.2, 29.8, 29.9, 50_000 if i == 19 else 100_000))
    opening = pd.DataFrame(rows, columns=["day", "symbol", "o", "h", "l", "c", "v"])
    frame = []
    for d in days:
        for s, px in (("HOT", 20.0), ("COLD", 30.0)):
            frame.append({"trade_date": d, "symbol": s, "open": px, "high": px + 1,
                          "low": px - 1, "close": px, "volume": 2e6, "adj_factor": 1.0,
                          "segment_id": 0})
    panel = Panel.from_frame(pd.DataFrame(frame))
    picks = orb.select(opening, panel, orb.OrbParams())
    assert [c.symbol for c in picks[days[-1]]] == ["HOT"]
    assert picks[days[-1]][0].direction == 1 and picks[days[-1]][0].level == 20.5


# ---- first candle + fair value gap --------------------------------------------------------

def test_fvg_finds_a_bullish_gap_that_breaks_the_opening_range():
    day = synth_sessions(1)[0]
    closes = np.full(390, 100.0)
    frame = day_frame(day, closes, spread=0.05)
    # bars 10, 11, 12: a gap - bar 12's low above bar 10's high, bar 11 closes above the range
    frame.iloc[10] = [100.0, 100.06, 99.95, 100.05, 1000, 100]
    frame.iloc[11] = [100.05, 100.60, 100.05, 100.55, 1000, 100]
    frame.iloc[12] = [100.55, 100.70, 100.30, 100.65, 1000, 100]
    grid = SessionGrid(frame)
    highs, lows = fvg.bar_extremes(frame, grid)
    setup = fvg.find_setup(grid, 0, highs, lows, fvg.FvgParams())
    assert setup is not None and setup.direction == 1 and setup.minute == 12
    assert setup.entry == pytest.approx(100.30) and setup.stop == pytest.approx(99.95)


# ---- insiders -----------------------------------------------------------------------------

def _trades(rows):
    return pd.DataFrame(rows, columns=["owner_cik", "issuer_cik", "filing_date", "trans_date",
                                       "code", "relationship", "shares", "price"])


def test_routine_insider_is_one_who_traded_the_same_month_three_years_running():
    rows = [("R", "C1", date(y, 3, 10), date(y, 3, 8), "S", "OFFICER", 100, 10.0)
            for y in (2013, 2014, 2015)]
    rows.append(("O", "C1", date(2015, 6, 1), date(2015, 6, 1), "P", "DIRECTOR", 100, 10.0))
    routine = routine_owners(_trades(rows))
    assert ("R", 2016) in routine and ("O", 2016) not in routine


def test_cluster_needs_two_people_within_the_window_and_enough_money():
    def buy(owner, day, shares=1000, rel="DIRECTOR"):
        return (owner, "0000000001", day, day, "P", rel, shares, 20.0)
    trades = _trades([buy("A", date(2020, 5, 1)), buy("B", date(2020, 5, 20)),
                      buy("C", date(2020, 8, 1)), buy("D", date(2020, 10, 1), shares=100),
                      buy("E", date(2020, 10, 5), shares=100),
                      buy("F", date(2020, 12, 1), rel="TENPERCENTOWNER"),
                      buy("G", date(2020, 12, 2), rel="TENPERCENTOWNER")])
    out = clusters(trades, {"0000000001": ["XYZ"]}, InsiderParams())
    assert out == {date(2020, 5, 20): {"XYZ"}}       # Oct is under $25k, Dec are 10% owners


def test_insider_parser_keeps_open_market_form4_trades_with_filing_date(tmp_path):
    sub = ("ACCESSION_NUMBER\tFILING_DATE\tPERIOD_OF_REPORT\tDOCUMENT_TYPE\tISSUERCIK\t"
           "ISSUERNAME\tISSUERTRADINGSYMBOL\n"
           "A1\t05-JAN-2017\t03-JAN-2017\t4\t320193\tAPPLE\tAAPL\n"
           "A2\t05-JAN-2017\t03-JAN-2017\t3\t320193\tAPPLE\tAAPL\n")
    owner = ("ACCESSION_NUMBER\tRPTOWNERCIK\tRPTOWNERNAME\tRPTOWNER_RELATIONSHIP\t"
             "RPTOWNER_TITLE\n"
             "A1\t111\tCOOK\tDirector,Officer\tCEO\nA2\t222\tX\tDirector\t\n")
    trans = ("ACCESSION_NUMBER\tNONDERIV_TRANS_SK\tTRANS_DATE\tTRANS_CODE\tTRANS_SHARES\t"
             "TRANS_PRICEPERSHARE\tTRANS_ACQUIRED_DISP_CD\n"
             "A1\t1\t03-JAN-2017\tP\t100\t116.15\tA\nA1\t2\t03-JAN-2017\tM\t50\t0\tA\n"
             "A2\t3\t03-JAN-2017\tP\t10\t116\tA\n")
    path = tmp_path / "2017q1_form345.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("SUBMISSION.tsv", sub)
        z.writestr("REPORTINGOWNER.tsv", owner)
        z.writestr("NONDERIV_TRANS.tsv", trans)
    rows = insiders.parse_quarter(path)
    assert rows == [("A1", date(2017, 1, 5), "0000320193", "AAPL", "0000000111",
                     "DIRECTOR,OFFICER", "CEO", date(2017, 1, 3), "P", 100.0, 116.15)]


# ---- 13F ----------------------------------------------------------------------------------

def test_cusips_match_on_implied_price_and_a_shared_name_word():
    period = date(2020, 3, 31)
    holdings = pd.DataFrame({"cusip": ["037833100", "999999999", "888888888"],
                             "period": [period] * 3,
                             "issuer": ["APPLE INC", "ACME CORP", "NOMATCH INC"],
                             "value": [254.0e3, 50.0e3, 10.0e3],
                             "shares": [1000.0, 1000.0, 1000.0]})
    closes = {period: {"AAPL": 254.29, "XYZ": 254.10, "ACME": 50.2, "ZZZ": 10.0}}
    names = {"AAPL": "Apple Inc. Common Stock", "XYZ": "Xyz Holdings", "ACME": "Acme Corp",
             "ZZZ": "Zeta Zeta"}
    assert form13f.match_cusips(holdings, closes, names) == {"037833100": "AAPL",
                                                            "999999999": "ACME"}


def test_quarter_helpers():
    assert previous_quarter_end(date(2020, 3, 31)) == date(2019, 12, 31)
    assert quarter_ends(date(2020, 1, 1), date(2020, 7, 1)) == [date(2020, 3, 31),
                                                               date(2020, 6, 30)]


def test_clone_scores_only_filings_already_public():
    days = synth_sessions(500)
    frame = []
    for t, d in enumerate(days):
        frame.append({"trade_date": d, "symbol": "UP", "open": 10 + t * 0.01,
                      "high": 10 + t * 0.01, "low": 10 + t * 0.01, "close": 10 + t * 0.01,
                      "volume": 1e6, "adj_factor": 1.0, "segment_id": 0})
    panel = Panel.from_frame(pd.DataFrame(frame))
    quarters = [date(2020, 3, 31), date(2020, 6, 30), date(2020, 9, 30), date(2020, 12, 31),
                date(2021, 3, 31)]
    filings = {"M": {q: Filing(q, q + timedelta(days=40), 300e6, {"UP": 300e6})
                     for q in quarters}}
    strat = Clone13F(filings, panel)
    assert strat.score("M", date(2021, 3, 31), date(2021, 5, 1)) is None   # not yet filed
    assert strat.score("M", date(2021, 3, 31), date(2021, 5, 20)) > 0


# ---- stock splits in the engine -----------------------------------------------------------

def _split_panel(ratio: float, dividend_step: float = 0.0) -> Panel:
    days = synth_sessions(12)
    frame = []
    for t, d in enumerate(days):
        px = 100.0 if t < 6 else 100.0 / ratio
        factor = (1.0 / ratio if t < 6 else 1.0) * (1 - dividend_step if t < 6 else 1.0)
        frame.append({"trade_date": d, "symbol": "SPLT", "open": px, "high": px, "low": px,
                      "close": px, "volume": 5e6, "adj_factor": factor, "segment_id": 0})
    return Panel.from_frame(pd.DataFrame(frame))


def test_a_held_position_survives_a_split_with_its_value_and_basis():
    panel = _split_panel(4.0)
    result = Backtester(panel, BacktestConfig()).run(BuyAndHold("SPLT", reinvest=False))
    eq = result.equity["equity"].astype(float)
    assert result.diagnostics["splits"] == 1
    assert eq.iloc[-1] == pytest.approx(eq.iloc[2], rel=1e-6)        # no fake 75% loss
    assert float(result.terminal["unrealized_at_end"]) == pytest.approx(0.0, abs=1.0)


def test_a_special_dividend_is_not_mistaken_for_a_split():
    panel = _split_panel(1.0 / 0.76)      # a 24% drop with no clean ratio: not a split
    result = Backtester(panel, BacktestConfig()).run(BuyAndHold("SPLT", reinvest=False))
    assert result.diagnostics["splits"] == 0


def test_ledger_split_keeps_basis_and_dates():
    ledger = TaxLedger()
    lot = ledger.buy(date(2020, 1, 2), "X", 10, D("100"))
    ledger.split(date(2020, 6, 1), "X", 2)
    assert lot.qty_remaining == D(20) and lot.basis_remaining == D("1000.00")
    disposals = ledger.sell(date(2021, 2, 1), "X", 20, D("60"))
    assert disposals[0].gain == D("200.00") and disposals[0].is_long_term
