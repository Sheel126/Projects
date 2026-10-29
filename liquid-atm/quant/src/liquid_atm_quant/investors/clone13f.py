"""Copying hedge funds: the best ideas of the managers whose 13F picks have been working
(lesson 03d §7).

The trap this avoids: a list of famous funds (Berkshire, Pershing, Scion, ...) is famous *because*
those funds did well, so backtesting it from 2016 reads the answer off today's reputation. Here
the managers are chosen every quarter by a rule that sees only filings already public:

1. **Concentrated books only**: at most 50 share positions, at least $250M reported, and at least
   70% of the reported value matched to a stock we have prices for.
2. **Score** = the compounded return of the manager's own reported holdings, value-weighted and
   held one quarter each, over the last four quarters (five consecutive filings needed). That is
   what copying them would have earned before the 45-day lag, which is the only skill we can buy.
3. **Pick** the top 10 managers and take each one's three largest positions (Cohen, Polk & Silli,
   "Best Ideas"), restricted to point-in-time Russell 1000 members. Equal weight, fully invested.
4. **When**: the first session at least 46 days after each quarter end, when every on-time 13F
   for that quarter is public. Hold until the next one.

Changing any field of `CloneParams` is a new trial.
"""

import bisect
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from liquid_atm_quant.backtest.panel import DataView, Panel
from liquid_atm_quant.backtest.strategy import PortfolioSnapshot
from liquid_atm_quant.investors.base import PortfolioStrategy


@dataclass(frozen=True)
class CloneParams:
    max_positions: int = 50
    min_book: float = 250e6
    min_coverage: float = 0.70
    score_quarters: int = 4
    managers: int = 10
    ideas_per_manager: int = 3
    filing_lag_days: int = 46


@dataclass
class Filing:
    period: date
    filed: date
    total: float
    holdings: dict[str, float]          # symbol -> value, mapped holdings only

    @property
    def coverage(self) -> float:
        return sum(self.holdings.values()) / self.total if self.total > 0 else 0.0


def quarter_ends(start: date, end: date) -> list[date]:
    out = []
    for year in range(start.year, end.year + 1):
        for month, day in ((3, 31), (6, 30), (9, 30), (12, 31)):
            q = date(year, month, day)
            if start <= q <= end:
                out.append(q)
    return out


def previous_quarter_end(q: date) -> date:
    return {3: date(q.year - 1, 12, 31), 6: date(q.year, 3, 31), 9: date(q.year, 6, 30),
            12: date(q.year, 9, 30)}[q.month]


def build_filings(holdings: pd.DataFrame, cusip_map: dict[str, str]) -> dict[str, dict[date, Filing]]:
    """cik -> {period: Filing}. If a manager filed twice for a period, the first filing counts."""
    frame = holdings.copy()
    frame["symbol"] = frame["cusip"].map(cusip_map)
    out: dict[str, dict[date, Filing]] = defaultdict(dict)
    for (cik, period, filed, acc), g in frame.groupby(["cik", "period", "filing_date",
                                                       "accession"], sort=True):
        if period in out[cik]:
            continue
        mapped = g.dropna(subset=["symbol"]).groupby("symbol")["value"].sum()
        out[cik][period] = Filing(period, filed, float(g["value"].sum()),
                                  {s: float(v) for s, v in mapped.items() if v > 0})
    return dict(out)


class Clone13F(PortfolioStrategy):
    name = "clone_13f"
    band = 0.5

    def __init__(self, filings: dict[str, dict[date, Filing]], panel: Panel,
                 params: CloneParams | None = None) -> None:
        super().__init__()
        self.params = params or CloneParams()
        self.filings = filings
        self._adj = panel.adjusted("close")
        self._sessions = panel.sessions
        self._index = panel.index
        self._done: set[date] = set()
        self.history: list[dict] = []

    def _price(self, symbol: str, when: date) -> float:
        j = self._index.get(symbol)
        if j is None:
            return np.nan
        t = bisect.bisect_right(self._sessions, when) - 1
        while t >= 0 and not np.isfinite(self._adj[t, j]):
            t -= 1                       # a holiday or a halt: the last price before it
        return float(self._adj[t, j]) if t >= 0 else np.nan

    def _quarter_return(self, f: Filing, until: date) -> float | None:
        weights, rets = [], []
        for symbol, value in f.holdings.items():
            a, b = self._price(symbol, f.period), self._price(symbol, until)
            if np.isfinite(a) and np.isfinite(b) and a > 0:
                weights.append(value)
                rets.append(b / a - 1)
        if not weights:
            return None
        return float(np.average(rets, weights=weights))

    def score(self, cik: str, latest: date, today: date) -> float | None:
        p = self.params
        by_period = self.filings[cik]
        periods = [latest]
        for _ in range(p.score_quarters):
            periods.insert(0, previous_quarter_end(periods[0]))
        if any(q not in by_period or by_period[q].filed >= today for q in periods):
            return None
        last = by_period[latest]
        if last.total < p.min_book or last.coverage < p.min_coverage:
            return None
        growth = 1.0
        for q, nxt in zip(periods[:-1], periods[1:]):
            r = self._quarter_return(by_period[q], nxt)
            if r is None:
                return None
            growth *= 1 + r
        return growth - 1

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        p = self.params
        today = view.today
        due = [q for q in quarter_ends(today - timedelta(days=200), today)
               if q + timedelta(days=p.filing_lag_days) <= today and q not in self._done]
        if not due:
            return None
        latest = max(due)
        self._done.update(due)
        scores = []
        for cik in self.filings:
            s = self.score(cik, latest, today)
            if s is not None:
                scores.append((s, cik))
        scores.sort(reverse=True)
        universe = set(view.universe())
        picks: list[str] = []
        chosen = scores[:p.managers]
        for _, cik in chosen:
            ranked = sorted(self.filings[cik][latest].holdings.items(), key=lambda kv: -kv[1])
            ideas = [s for s, _ in ranked if s in universe][:p.ideas_per_manager]
            picks.extend(s for s in ideas if s not in picks)
        self.history.append({"quarter": str(latest), "rebalanced": str(today),
                             "eligible_managers": len(scores),
                             "managers": [c for _, c in chosen],
                             "scores": [round(s, 4) for s, _ in chosen], "names": picks})
        if not picks:
            return None
        return {s: 1.0 / len(picks) for s in picks}

    def diagnostics(self) -> dict:
        return {"rebalances": self.history, "params": asdict(self.params)}


__all__ = ["Clone13F", "CloneParams", "Filing", "build_filings", "previous_quarter_end",
           "quarter_ends"]
