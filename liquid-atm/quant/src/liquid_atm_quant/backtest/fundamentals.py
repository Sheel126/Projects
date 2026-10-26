"""Point-in-time fundamentals for the backtest (lesson 03b §2).

`fundamental_facts` holds each figure as first reported, with its filing date. This module turns
those raw facts into what a strategy asks for - trailing-twelve-month (TTM) earnings, the latest
balance sheet, quarter-over-year growth - **as known at the close of a given day**.

Three pieces of accounting plumbing, each a classic source of silent look-ahead:

* **Quarters from year-to-date figures.** 10-Qs report cash flow (and often income) only
  year-to-date, and nobody files a Q4 10-Q. A quarter is therefore either a reported ~3-month
  period or the difference of two cumulative periods sharing a fiscal-year start (9M - 6M,
  FY - 9M = Q4). A derived quarter is known only once *both* filings are out.
* **Known means filed before today.** The filing date has no time of day, so a fact filed on day
  D is usable from the close of D+1 onward (`known < today`), never on D.
* **Stale or borrowed identities.** If a company's latest quarter is more than `STALE_DAYS` old it
  has stopped filing (acquired, delisted, or a reused ticker now pointing elsewhere): no snapshot.
  And a symbol's CIK is applied only to the symbol's latest identity segment in the panel, so a
  ticker reused by a new company does not inherit the old company's books, or vice versa.
"""

import bisect
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import psycopg

from liquid_atm_quant.backtest.panel import DataView, Panel

QUARTER_DAYS = (75, 105)
"""A ~3-month period, allowing for 52/53-week fiscal calendars."""
STALE_DAYS = 200
"""No new quarter for this long: the company is not filing, so its numbers are not live."""
INSTANT_STALE_DAYS = 400

_FACTS_SQL = """
    SELECT i.symbol, f.concept, f.period_start, f.period_end, f.value::float8, f.filed
    FROM fundamental_facts f JOIN instruments i ON i.cik = f.cik
    WHERE i.symbol = ANY(%s)"""


@dataclass(frozen=True)
class Point:
    end: date
    value: float
    known: date
    """First date the value was public: the filing date (or the later of two, if derived)."""


def quarterize(durations: list[tuple[date, date, float, date]]) -> list[Point]:
    """3-month values from reported quarters plus differences of cumulative periods.

    `durations` is (start, end, value, filed). When a quarter is available both ways, the version
    known first wins: both are first reports of the same number.
    """
    by_end: dict[date, Point] = {}

    def offer(point: Point) -> None:
        current = by_end.get(point.end)
        if current is None or point.known < current.known:
            by_end[point.end] = point

    by_start: dict[date, list[tuple[date, float, date]]] = defaultdict(list)
    for start, end, value, filed in durations:
        days = (end - start).days
        if QUARTER_DAYS[0] <= days <= QUARTER_DAYS[1]:
            offer(Point(end, value, filed))
        by_start[start].append((end, value, filed))
    for periods in by_start.values():
        periods.sort()
        for (end_a, value_a, filed_a), (end_b, value_b, filed_b) in zip(periods, periods[1:]):
            if QUARTER_DAYS[0] <= (end_b - end_a).days <= QUARTER_DAYS[1]:
                offer(Point(end_b, value_b - value_a, max(filed_a, filed_b)))
    return sorted(by_end.values(), key=lambda p: p.end)


@dataclass(frozen=True)
class Snapshot:
    """What was public about one company at the close of `as_of`. Money in dollars."""

    as_of: date
    latest_quarter_end: date
    ttm: dict[str, float]
    """Sum of the latest four consecutive quarters per duration concept (missing if any gap)."""
    ttm_prior: dict[str, float]
    """The same four-quarter sum one year earlier: quarters 5-8 back."""
    quarters: dict[str, list[float]]
    """Up to the last 8 consecutive quarterly values, oldest first."""
    instant: dict[str, float]
    shares_known: date | None = None

    def get(self, concept: str, default: float | None = None) -> float | None:
        return self.ttm.get(concept, self.instant.get(concept, default))

    @property
    def debt(self) -> float:
        """Long plus short-term debt. A company with no debt often files no debt tag: zero."""
        return self.instant.get("lt_debt", 0.0) + self.instant.get("st_debt", 0.0)

    @property
    def cash(self) -> float:
        return self.instant.get("cash", 0.0)


@dataclass
class _Company:
    quarters: dict[str, list[Point]] = field(default_factory=dict)
    instants: dict[str, list[Point]] = field(default_factory=dict)
    known_dates: list[date] = field(default_factory=list)
    cache: dict[int, Snapshot | None] = field(default_factory=dict)


class Fundamentals:
    """Fundamental snapshots keyed by (symbol, day), safe to share between strategies and runs."""

    def __init__(self, rows: list[tuple], allowed_segment: dict[str, int] | None = None) -> None:
        durations: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        instants: dict[str, dict[str, list[Point]]] = defaultdict(lambda: defaultdict(list))
        for symbol, concept, start, end, value, filed in rows:
            if start is None:
                instants[symbol][concept].append(Point(end, value, filed))
            else:
                durations[symbol][concept].append((start, end, value, filed))
        self._companies: dict[str, _Company] = {}
        for symbol in set(durations) | set(instants):
            company = _Company(
                quarters={c: quarterize(d) for c, d in durations[symbol].items()},
                instants={c: sorted(p, key=lambda x: x.end) for c, p in instants[symbol].items()})
            known = {p.known for series in (*company.quarters.values(), *company.instants.values())
                     for p in series}
            company.known_dates = sorted(known)
            self._companies[symbol] = company
        self.allowed_segment = allowed_segment or {}

    @classmethod
    def from_db(cls, conn: psycopg.Connection, panel: Panel) -> "Fundamentals":
        with conn.cursor() as cur:
            cur.execute(_FACTS_SQL, (panel.symbols,))
            rows = cur.fetchall()
        return cls(rows, latest_segments(panel))

    @property
    def symbols(self) -> set[str]:
        return set(self._companies)

    def snapshot(self, view: DataView, symbol: str) -> Snapshot | None:
        company = self._companies.get(symbol)
        if company is None:
            return None
        allowed = self.allowed_segment.get(symbol)
        if allowed is not None and view.segment(symbol) != allowed:
            return None
        return self.at(symbol, view.today)

    def at(self, symbol: str, today: date) -> Snapshot | None:
        """The snapshot as of the close of `today`, ignoring segments (tests and research)."""
        company = self._companies.get(symbol)
        if company is None:
            return None
        n_known = bisect.bisect_left(company.known_dates, today)     # strictly before today
        if n_known == 0:
            return None
        cached = company.cache.get(n_known, ...)
        if cached is ...:
            cached = _build(company, company.known_dates[n_known - 1] + timedelta(days=1))
            company.cache[n_known] = cached
        if cached is None or (today - cached.latest_quarter_end).days > STALE_DAYS:
            return None
        return cached


def _consecutive(points: list[Point]) -> list[Point]:
    """The longest run of quarters ending at the latest one with no missing quarter in between."""
    if not points:
        return []
    run = [points[-1]]
    for p in reversed(points[:-1]):
        if QUARTER_DAYS[0] <= (run[-1].end - p.end).days <= QUARTER_DAYS[1]:
            run.append(p)
        else:
            break
    return run[::-1]


def _build(company: _Company, cutoff: date) -> Snapshot | None:
    """Everything known strictly before `cutoff` (cutoff = the day after the last filing)."""
    quarters: dict[str, list[float]] = {}
    ttm: dict[str, float] = {}
    ttm_prior: dict[str, float] = {}
    latest_end: date | None = None
    for concept, series in company.quarters.items():
        known = [p for p in series if p.known < cutoff]
        run = _consecutive(known)[-8:]
        if not run:
            continue
        quarters[concept] = [p.value for p in run]
        if len(run) >= 4:
            ttm[concept] = sum(p.value for p in run[-4:])
        if len(run) >= 8:
            ttm_prior[concept] = sum(p.value for p in run[-8:-4])
        if concept in ("net_income", "revenue"):
            latest_end = max(latest_end or run[-1].end, run[-1].end)
    if latest_end is None:
        return None

    instant: dict[str, float] = {}
    shares_known = None
    for concept, series in company.instants.items():
        known = [p for p in series if p.known < cutoff]
        if not known:
            continue
        latest = max(known, key=lambda p: (p.end, p.known))
        if (cutoff - latest.end).days > INSTANT_STALE_DAYS:
            continue
        instant[concept] = latest.value
        if concept == "shares_out":
            shares_known = latest.known
    return Snapshot(cutoff, latest_end, ttm, ttm_prior, quarters, instant, shares_known)


def latest_segments(panel: Panel) -> dict[str, int]:
    """Each symbol's last identity segment in the panel: the one its current CIK belongs to."""
    out: dict[str, int] = {}
    seg = panel.segment_id
    for j, symbol in enumerate(panel.symbols):
        live = seg[:, j][seg[:, j] >= 0]
        if live.size:
            out[symbol] = int(live[-1])
    return out


def market_cap(view: DataView, symbol: str, snap: Snapshot) -> float | None:
    """Shares outstanding x today's price, robust to splits after the share count was reported.

    The share count is as of its filing; a 4-for-1 split since then would make `shares x price`
    wrong by 4x. So the price used is the raw close on the day the count became known, carried
    forward by the adjusted-price return since. (The adjusted series also folds in dividends,
    which overstates the cap by the yield since the filing - at most a couple of percent.)
    """
    shares = snap.instant.get("shares_out")
    if not shares or shares <= 0:
        return None
    price_today = view.latest("close", symbol, adjusted=True)
    if not np.isfinite(price_today):
        return None
    sessions = view.panel.sessions
    if snap.shares_known is not None and snap.shares_known >= sessions[0]:
        i = min(bisect.bisect_right(sessions, snap.shares_known) - 1, view.t)
        j = view.panel.index[symbol]
        raw_then = view.panel.column("close")[i, j]
        adj_then = view.panel.adjusted("close")[i, j]
        if np.isfinite(raw_then) and np.isfinite(adj_then) and adj_then > 0:
            return float(shares * raw_then * price_today / adj_then)
    raw_today = view.latest("close", symbol)
    return float(shares * raw_today) if np.isfinite(raw_today) else None


__all__ = ["Fundamentals", "Point", "Snapshot", "latest_segments", "market_cap", "quarterize"]
