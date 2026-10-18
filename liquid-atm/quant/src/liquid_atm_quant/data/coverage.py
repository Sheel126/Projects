"""Survivorship coverage (lesson 01 §4): of each historical snapshot's members, how many have prices?"""

from dataclasses import dataclass
from datetime import date

import psycopg

ALPACA_HISTORY_START = date(2016, 1, 4)


@dataclass(frozen=True)
class CoverageRow:
    index_name: str
    year: int
    snapshots: int
    members: int
    covered: int

    @property
    def ratio(self) -> float:
        return self.covered / self.members if self.members else 0.0


def coverage_by_year(conn: psycopg.Connection, since: date = ALPACA_HISTORY_START) -> list[CoverageRow]:
    """A member is covered if it has a bar within 8 calendar days (~5 sessions) of the snapshot.

    S&P 500 has ~2,700 change-date snapshots; we sample the first snapshot of each month.
    """
    with conn.cursor() as cur:
        cur.execute("""
            WITH snaps AS (
                SELECT DISTINCT ON (index_name, date_trunc('month', as_of_date)) index_name, as_of_date
                FROM universe_snapshots WHERE as_of_date >= %(since)s
                ORDER BY index_name, date_trunc('month', as_of_date), as_of_date),
            per_member AS (
                SELECT s.index_name, s.as_of_date, m.symbol,
                       EXISTS (SELECT 1 FROM tradable_bars b
                               WHERE b.symbol = m.symbol
                                 AND b.trade_date BETWEEN s.as_of_date - 8 AND s.as_of_date + 8) AS covered
                FROM snaps s JOIN universe_membership m USING (index_name, as_of_date))
            SELECT index_name, extract(year FROM as_of_date)::int,
                   count(DISTINCT as_of_date), count(*), count(*) FILTER (WHERE covered)
            FROM per_member GROUP BY 1, 2 ORDER BY 1, 2""", {"since": since})
        return [CoverageRow(*r) for r in cur.fetchall()]


def uncovered_members(conn: psycopg.Connection, index_name: str, as_of: date) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT m.symbol FROM universe_membership m
            WHERE m.index_name = %s AND m.as_of_date = %s
              AND NOT EXISTS (SELECT 1 FROM tradable_bars b WHERE b.symbol = m.symbol
                              AND b.trade_date BETWEEN m.as_of_date - 8 AND m.as_of_date + 8)
            ORDER BY 1""", (index_name, as_of))
        return [r[0] for r in cur.fetchall()]
