"""Point-in-time fundamentals (lesson 03b §2): first report wins, nothing is known early.

The tests that matter most are the look-ahead ones: a fact filed on day D is invisible at the close
of D and visible at the close of D+1, and adding later facts never changes an earlier snapshot.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from liquid_atm_quant.backtest.fundamentals import (Fundamentals, latest_segments, market_cap,
                                                    quarterize)
from liquid_atm_quant.backtest.panel import Panel
from liquid_atm_quant.data.fundamentals import candidate_ciks, choose, normalize_name, parse_company

D = date


def quarter_ends(first: date, n: int) -> list[date]:
    """Calendar quarter ends starting at `first` (a quarter end)."""
    ends, y, m = [], first.year, first.month
    for _ in range(n):
        last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
        ends.append(last)
        m += 3
        if m > 12:
            m -= 12
            y += 1
    return ends


def company_rows(symbol: str, ends: list[date], ni: list[float], lag: int = 30,
                 extra: dict[str, float] | None = None) -> list[tuple]:
    """10-Q style facts: a 3-month duration per quarter for each income concept, plus instants."""
    rows = []
    for end, value in zip(ends, ni):
        start, filed = end - timedelta(days=90), end + timedelta(days=lag)
        for concept, v in (("net_income", value), ("revenue", value * 10),
                           ("operating_income", value * 1.5), ("cfo", value * 1.2),
                           ("capex", value * 0.2)):
            rows.append((symbol, concept, start, end, v, filed))
        instants = {"equity": 1000.0, "lt_debt": 200.0, "cash": 100.0, "current_assets": 400.0,
                    "current_liabilities": 300.0, "ppe_net": 500.0, "shares_out": 100.0,
                    **(extra or {})}
        for concept, v in instants.items():
            rows.append((symbol, concept, None, end, v, filed))
    return rows


# ---- quarterize --------------------------------------------------------------------------

def test_quarters_come_from_reports_and_from_year_to_date_differences():
    fy = D(2020, 1, 1)
    durations = [
        (fy, D(2020, 3, 31), 10.0, D(2020, 5, 1)),           # Q1 reported directly
        (fy, D(2020, 6, 30), 25.0, D(2020, 8, 1)),           # 6M YTD -> Q2 = 15
        (fy, D(2020, 9, 30), 45.0, D(2020, 11, 1)),          # 9M YTD -> Q3 = 20
        (fy, D(2020, 12, 31), 70.0, D(2021, 2, 20)),         # FY -> Q4 = 25, no Q4 10-Q exists
    ]
    q = quarterize(durations)
    assert [(p.end, p.value) for p in q] == [(D(2020, 3, 31), 10.0), (D(2020, 6, 30), 15.0),
                                             (D(2020, 9, 30), 20.0), (D(2020, 12, 31), 25.0)]
    # A derived quarter is known only when the later of its two filings is out.
    assert q[3].known == D(2021, 2, 20)


def test_the_version_of_a_quarter_known_first_wins():
    fy = D(2020, 1, 1)
    durations = [(fy, D(2020, 3, 31), 10.0, D(2020, 5, 1)),
                 (fy, D(2020, 6, 30), 25.0, D(2020, 9, 1)),               # YTD filed late
                 (D(2020, 4, 1), D(2020, 6, 30), 15.0, D(2020, 8, 1))]    # 3M filed earlier
    q = {p.end: p for p in quarterize(durations)}
    assert q[D(2020, 6, 30)].known == D(2020, 8, 1)


# ---- snapshots ---------------------------------------------------------------------------

def test_a_fact_is_invisible_on_its_filing_day_and_visible_the_day_after():
    ends = quarter_ends(D(2019, 3, 31), 4)
    f = Fundamentals(company_rows("AAA", ends, [1.0, 2.0, 3.0, 4.0]))
    last_filed = ends[-1] + timedelta(days=30)
    before = f.at("AAA", last_filed)
    after = f.at("AAA", last_filed + timedelta(days=1))
    assert "net_income" not in before.ttm                  # only three quarters known
    assert after.ttm["net_income"] == 10.0


def test_ttm_needs_four_consecutive_quarters_and_prior_ttm_needs_eight():
    ends = quarter_ends(D(2018, 3, 31), 8)
    f = Fundamentals(company_rows("AAA", ends, [1, 1, 1, 1, 2, 2, 2, 2]))
    snap = f.at("AAA", ends[-1] + timedelta(days=60))
    assert snap.ttm["net_income"] == 8 and snap.ttm_prior["net_income"] == 4
    assert snap.quarters["net_income"] == [1, 1, 1, 1, 2, 2, 2, 2]

    gap = ends[:5] + ends[6:]                               # one quarter never filed
    f = Fundamentals(company_rows("BBB", gap, [1] * 7))
    snap = f.at("BBB", gap[-1] + timedelta(days=60))
    assert "net_income" not in snap.ttm                     # the run since the gap is 2 long


def test_a_company_that_stopped_filing_has_no_snapshot():
    ends = quarter_ends(D(2018, 3, 31), 4)
    f = Fundamentals(company_rows("AAA", ends, [1.0] * 4))
    assert f.at("AAA", ends[-1] + timedelta(days=150)) is not None
    assert f.at("AAA", ends[-1] + timedelta(days=260)) is None


def test_later_facts_never_change_an_earlier_snapshot():
    ends = quarter_ends(D(2017, 3, 31), 16)
    rows = company_rows("AAA", ends, list(np.linspace(1, 16, 16)))
    full = Fundamentals(rows)
    for probe in (D(2018, 6, 15), D(2019, 2, 1), D(2020, 8, 30)):
        truncated = Fundamentals([r for r in rows if r[5] < probe])
        a, b = full.at("AAA", probe), truncated.at("AAA", probe)
        assert (a.ttm, a.ttm_prior, a.quarters) == (b.ttm, b.ttm_prior, b.quarters)
        assert a.instant == b.instant


# ---- segments and market cap -------------------------------------------------------------

def _panel(n: int, closes: list[float], factors: list[float], segments: list[int]) -> Panel:
    days, day = [], D(2020, 1, 2)
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    frame = pd.DataFrame({"trade_date": days, "symbol": "AAA", "open": closes, "high": closes,
                          "low": closes, "close": closes, "volume": 1e6, "adj_factor": factors,
                          "segment_id": segments})
    return Panel.from_frame(frame, days)


def test_market_cap_survives_a_split_after_the_share_count_was_reported():
    # 100 shares reported at $40; a 2-for-1 split on session 10 halves the raw price.
    closes = [40.0] * 10 + [20.0] * 10
    factors = [0.5] * 10 + [1.0] * 10                       # back-adjusted: pre-split halves
    panel = _panel(20, closes, factors, [0] * 20)
    shares_filed = panel.sessions[3]
    rows = company_rows("AAA", quarter_ends(D(2019, 3, 31), 4), [1.0] * 4)
    rows = [r for r in rows if r[1] != "shares_out"] + [
        ("AAA", "shares_out", None, D(2019, 12, 31), 100.0, shares_filed)]
    f = Fundamentals(rows)
    view = panel.view(15)
    snap = f.at("AAA", view.today)
    assert market_cap(view, "AAA", snap) == 4000.0          # 200 shares x $20, not 100 x $20


def test_fundamentals_apply_only_to_the_symbols_latest_identity():
    panel = _panel(20, [10.0] * 20, [1.0] * 20, [3] * 10 + [7] * 10)   # ticker reused at 10
    rows = company_rows("AAA", quarter_ends(D(2019, 3, 31), 4), [1.0] * 4)
    f = Fundamentals(rows, latest_segments(panel))
    assert f.snapshot(panel.view(5), "AAA") is None         # the old company's segment
    assert f.snapshot(panel.view(15), "AAA") is not None


# ---- import: parsing and symbol resolution ------------------------------------------------

def test_parse_company_keeps_the_first_report_across_aliases():
    body = {"cik": 42, "facts": {"us-gaap": {
        "SalesRevenueNet": {"units": {"USD": [
            {"start": "2017-01-01", "end": "2017-03-31", "val": 100, "filed": "2017-05-01",
             "form": "10-Q", "accn": "a"}]}},
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            # the same quarter, repeated (restated) as a comparative a year later
            {"start": "2017-01-01", "end": "2017-03-31", "val": 105, "filed": "2018-05-01",
             "form": "10-Q", "accn": "b"},
            {"start": "2018-01-01", "end": "2018-03-31", "val": 120, "filed": "2018-05-01",
             "form": "10-Q", "accn": "b"}]}},
        "Assets": {"units": {"USD": [
            {"end": "2018-03-31", "val": 900, "filed": "2018-05-01", "form": "10-Q"},
            {"end": "2018-03-31", "val": 900, "filed": "2018-05-01", "form": "8-K"}]}},
    }}}
    facts = {(f.concept, f.period_end): f for f in parse_company(body)}
    assert facts[("revenue", D(2017, 3, 31))].value == 100       # first report, not restated
    assert facts[("revenue", D(2018, 3, 31))].value == 120
    assert facts[("assets", D(2018, 3, 31))].period_start is None
    assert all(f.cik == "0000000042" for f in facts.values())


def test_name_normalization_and_cik_choice():
    assert normalize_name("Apple Inc. Common Stock") == normalize_name("APPLE INC") == "apple"
    assert normalize_name("ExxonMobil Holdings Corporation") == normalize_name("EXXON MOBIL CORP")
    names = {"0000000001": "EXXON MOBIL CORP", "0000000002": "ExxonMobil Holdings Corp"}
    cands = candidate_ciks({"XOM": "ExxonMobil Holdings Corporation"}, {"XOM": "0000000002"}, names)
    assert cands == {"XOM": [("0000000002", "ticker")]}            # two name matches: ambiguous
    cands = candidate_ciks({"XOM": "Exxon Mobil Corporation"}, {"XOM": "0000000002"},
                           {"0000000001": "EXXON MOBIL CORP",
                            "0000000002": "ExxonMobil Holdco Inc"})
    assert choose(cands, {"0000000001": 60, "0000000002": 2}) == {"XOM": ("0000000001", "name")}
