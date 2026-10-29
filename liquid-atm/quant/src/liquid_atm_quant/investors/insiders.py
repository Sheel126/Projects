"""Copying insiders: clustered, opportunistic open-market purchases (lesson 03d §6).

The rules, written down before the first run. Changing any field of `InsiderParams` is a new trial.

1. **Whose buys count.** Officers and directors (not shareholders who are only 10% owners),
   open-market purchases (Form 4 code P), dated by when the filing became public.
2. **Drop routine traders** (Cohen, Malloy & Pomorski 2012). An insider is routine in year Y if
   they traded in the same calendar month in each of the three years before Y. Their trades are
   predictable - a bonus month, a plan - and the paper finds they carry no information. Everyone
   else is opportunistic. Insiders with less than three years of history cannot be routine, so
   they count (CMP excluded them; that is the one departure, and it adds signals rather than
   choosing among them).
3. **A cluster**: at least two different opportunistic officers or directors buying the same
   company within 30 calendar days, at least $25,000 between them. One buy can be a gesture;
   two people independently putting their own money in is the stronger signal (Lakonishok & Lee
   2001; Alldredge & Blank 2019).
4. **Trade** the session after the cluster's filing date, if the company is in the point-in-time
   Russell 1000 that day. Hold each name 126 sessions (about six months) from its latest
   cluster; a new cluster restarts the clock.
5. **Size**: 5% per name, at most 20. Everything not in insider names sits in SPY, so on a quiet
   month the strategy is the benchmark rather than cash, and every result is "SPY plus insider
   picks" against SPY.
"""

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta

import pandas as pd

from liquid_atm_quant.backtest.panel import DataView
from liquid_atm_quant.backtest.strategy import PortfolioSnapshot
from liquid_atm_quant.investors.base import PortfolioStrategy


@dataclass(frozen=True)
class InsiderParams:
    min_insiders: int = 2
    window_days: int = 30
    min_cluster_value: float = 25_000.0
    routine_years: int = 3
    hold_sessions: int = 126
    weight: float = 0.05
    max_names: int = 20
    core: str = "SPY"


def routine_owners(trades: pd.DataFrame, years: int = 3) -> set[tuple[str, int]]:
    """(owner_cik, year) pairs where the owner is routine: in every one of the `years` previous
    calendar years they traded in some common calendar month."""
    months: dict[str, dict[int, set[int]]] = defaultdict(lambda: defaultdict(set))
    for owner, when in zip(trades["owner_cik"], trades["trans_date"]):
        if isinstance(when, date):
            months[owner][when.year].add(when.month)
    out = set()
    for owner, by_year in months.items():
        for year in range(min(by_year) + years, max(by_year) + 2):
            common = set(range(1, 13))
            for back in range(1, years + 1):
                common &= by_year.get(year - back, set())
                if not common:
                    break
            if common:
                out.add((owner, year))
    return out


def clusters(trades: pd.DataFrame, cik_to_symbols: dict[str, list[str]],
             params: InsiderParams) -> dict[date, set[str]]:
    """Filing date -> symbols whose purchase cluster became public that day."""
    p = params
    routine = routine_owners(trades, p.routine_years)
    buys = trades[(trades["code"] == "P")
                  & trades["relationship"].str.contains("OFFICER|DIRECTOR", na=False)].copy()
    buys["value"] = buys["shares"] * buys["price"].fillna(0.0)
    buys = buys[[(o, d.year) not in routine
                 for o, d in zip(buys["owner_cik"], buys["filing_date"])]]
    out: dict[date, set[str]] = defaultdict(set)
    window = timedelta(days=p.window_days)
    for cik, g in buys.groupby("issuer_cik"):
        symbols = cik_to_symbols.get(cik)
        if not symbols:
            continue
        g = g.sort_values("filing_date")
        filed = list(g["filing_date"])
        owners, values = list(g["owner_cik"]), list(g["value"])
        for i, day in enumerate(filed):
            if i and filed[i - 1] == day:
                continue                     # evaluate each filing date once, with all its rows
            last = i
            while last + 1 < len(filed) and filed[last + 1] == day:
                last += 1
            lo = i
            while lo > 0 and filed[lo - 1] > day - window:
                lo -= 1
            people = set(owners[lo:last + 1])
            value = sum(values[lo:last + 1])
            if len(people) >= p.min_insiders and value >= p.min_cluster_value:
                out[day].update(symbols)
    return dict(out)


class InsiderCluster(PortfolioStrategy):
    name = "insider_cluster"
    band = 0.5
    band_overrides = {"SPY": 0.01}
    """The core is resized every time a name comes or goes: that is where the cash for a new
    position comes from. The names themselves are never trimmed."""

    def __init__(self, triggers: dict[date, set[str]], params: InsiderParams | None = None) -> None:
        super().__init__()
        self.params = params or InsiderParams()
        self.triggers = triggers
        self._pending = sorted(triggers)
        self._cursor = 0
        self._held: dict[str, int] = {}          # symbol -> session index its clock started
        self._t = -1
        self.signals = self.entered = self.skipped_full = self.skipped_universe = 0

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        p = self.params
        self._t += 1
        today = view.today
        fresh: set[str] = set()
        while self._cursor < len(self._pending) and self._pending[self._cursor] <= today:
            fresh |= self.triggers[self._pending[self._cursor]]
            self._cursor += 1
        changed = self._t == 0
        universe = set(view.universe()) if fresh else set()
        for symbol in sorted(fresh):
            self.signals += 1
            if symbol not in universe:
                self.skipped_universe += 1
                continue
            if symbol in self._held:
                self._held[symbol] = self._t
                continue
            if len(self._held) >= p.max_names:
                self.skipped_full += 1
                continue
            self._held[symbol] = self._t
            self.entered += 1
            changed = True
        for symbol, started in list(self._held.items()):
            if self._t - started >= p.hold_sessions:
                del self._held[symbol]
                changed = True
        if not changed:
            return None
        weights = {s: p.weight for s in self._held}
        weights[p.core] = max(0.0, 1.0 - p.weight * len(self._held))
        return weights

    def diagnostics(self) -> dict:
        return {"signals": self.signals, "entered": self.entered,
                "skipped_full": self.skipped_full, "skipped_not_in_universe": self.skipped_universe,
                "params": asdict(self.params)}


__all__ = ["InsiderCluster", "InsiderParams", "clusters", "routine_owners"]
