"""Synthetic 10-Q facts for the Phase 3b strategy tests: every ratio is chosen in advance."""

from datetime import date, timedelta

QUARTER_ENDS = [date(2018, 3, 31), date(2018, 6, 30), date(2018, 9, 30), date(2018, 12, 31),
                date(2019, 3, 31), date(2019, 6, 30), date(2019, 9, 30), date(2019, 12, 31)]
"""Eight quarters, the last filed 2020-01-30: live (not stale) through mid-2020."""

LATER_ENDS = [date(2019, 3, 31), date(2019, 6, 30), date(2019, 9, 30), date(2019, 12, 31),
              date(2020, 3, 31), date(2020, 6, 30), date(2020, 9, 30), date(2020, 12, 31)]
"""The same eight quarters a year on: for tests that need a year of price history first. The
last two are filed after the panel's late-2020 test sessions, so the newest known is Q2 2020."""


def company(symbol: str, ni: list[float] | float = 1e6, op_margin: float = 1.5,
            revenue_mult: float = 10.0, cfo_mult: float = 1.2, capex_mult: float = 0.2,
            equity: float = 20e6, debt: float = 2e6, cash: float = 1e6, shares: float = 1e6,
            current_assets: float = 10e6, current_liabilities: float = 6e6, ppe: float = 8e6,
            ends: list[date] | None = None, lag: int = 30) -> list[tuple]:
    """(symbol, concept, start, end, value, filed) rows: 3-month durations plus instants.

    `ni` is quarterly net income (a list, oldest first, or one value for every quarter); operating
    income, revenue, CFO and capex are fixed multiples of it.
    """
    ends = ends or QUARTER_ENDS
    values = ni if isinstance(ni, list) else [ni] * len(ends)
    rows = []
    for end, v in zip(ends, values):
        start, filed = end - timedelta(days=90), end + timedelta(days=lag)
        for concept, x in (("net_income", v), ("operating_income", v * op_margin),
                           ("revenue", abs(v) * revenue_mult), ("cfo", v * cfo_mult),
                           ("capex", abs(v) * capex_mult)):
            rows.append((symbol, concept, start, end, x, filed))
        for concept, x in (("equity", equity), ("lt_debt", debt), ("cash", cash),
                           ("shares_out", shares), ("current_assets", current_assets),
                           ("current_liabilities", current_liabilities), ("ppe_net", ppe)):
            rows.append((symbol, concept, None, end, x, filed))
    return rows
