"""Data-quality checks (lesson 01 §6). Each run writes issues tagged with a run_id.

Gate rule: zero `error` issues. Warnings are reviewed, never auto-deleted: a real -60% day
removed as an "outlier" is survivorship bias sneaking back in.

All price checks read `tradable_bars` (volume > 0), because Alpaca pads delisted symbols with
frozen zero-volume bars forever (lesson 01 §5).
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import psycopg

from liquid_atm_quant.data import yahoo
from liquid_atm_quant.infra.rate_limiter import SlidingWindowRateLimiter

LARGE_MOVE = 0.40
TICKER_GAP_DAYS = 20
PADDING_RUN = 3
CROSSCHECK_TOLERANCE = 0.015

# Snapshot in force on a bar's date, per index: the membership the bot would have traded.
_MEMBER_AT_BAR = """
    EXISTS (SELECT 1 FROM universe_snapshots s
            JOIN universe_membership m ON m.index_name = s.index_name AND m.as_of_date = s.as_of_date
            WHERE m.symbol = {bar}.symbol
              AND s.as_of_date = (SELECT max(x.as_of_date) FROM universe_snapshots x
                                  WHERE x.index_name = s.index_name AND x.as_of_date <= {bar}.trade_date))"""

CHECKS: dict[str, str] = {
    # A snapshot that parsed to nothing would empty the universe until the next one (lesson 03d
    # §9). The panel skips them; this makes sure they are seen.
    "empty_snapshot": """
        SELECT index_name, as_of_date, 'warn', jsonb_build_object('source', source)
        FROM universe_snapshots WHERE member_count = 0""",

    "ohlc_sanity": """
        SELECT b.symbol, b.trade_date, 'error',
               jsonb_build_object('open', b.open, 'high', b.high, 'low', b.low, 'close', b.close)
        FROM daily_bars b
        WHERE b.low <= 0 OR b.low > least(b.open, b.close) OR b.high < greatest(b.open, b.close)""",

    # Isolated zero-volume sessions (halts). Long frozen runs are reported by `frozen_padding`.
    "zero_volume": f"""
        WITH z AS (
            SELECT b.symbol, b.trade_date,
                   count(*) OVER (PARTITION BY b.symbol, b.open, b.high, b.low, b.close) AS run_size
            FROM daily_bars b LEFT JOIN instruments i USING (symbol)
            WHERE b.volume = 0 AND coalesce(i.asset_class, 'us_equity') <> 'index')
        SELECT symbol, trade_date, 'warn', '{{}}'::jsonb FROM z WHERE run_size < {PADDING_RUN}""",

    # Post-delisting placeholders: many sessions sharing one frozen OHLC with no volume.
    "frozen_padding": f"""
        WITH z AS (
            SELECT b.symbol, b.close, count(*) AS sessions, min(b.trade_date) AS from_date,
                   max(b.trade_date) AS to_date
            FROM daily_bars b LEFT JOIN instruments i USING (symbol)
            WHERE b.volume = 0 AND coalesce(i.asset_class, 'us_equity') <> 'index'
              AND b.open = b.close AND b.high = b.close AND b.low = b.close
            GROUP BY b.symbol, b.close)
        SELECT symbol, from_date, 'warn',
               jsonb_build_object('sessions', sessions, 'frozen_price', close, 'until', to_date)
        FROM z WHERE sessions >= {PADDING_RUN}""",

    # Gaps in REAL trading, measured in sessions. A gap that starts exactly where the symbol was
    # marked delisted is an EXPLAINED identity change (ticker reuse, handled by bar_segments) and
    # is only a warning. An unexplained hole in an index member's history is an error: the bot
    # would have traded across it.
    "ticker_gap": f"""
        WITH cal AS (SELECT trade_date, row_number() OVER (ORDER BY trade_date) AS rn FROM trading_calendar),
        seq AS (
            SELECT b.symbol, b.trade_date, c.rn,
                   lag(c.rn) OVER (PARTITION BY b.symbol ORDER BY b.trade_date) AS prev_rn,
                   lag(b.trade_date) OVER (PARTITION BY b.symbol ORDER BY b.trade_date) AS prev_date
            FROM tradable_bars b JOIN cal c USING (trade_date))
        SELECT seq.symbol, seq.trade_date,
               CASE WHEN {_MEMBER_AT_BAR.format(bar='seq')}
                         AND i.delisted_on IS DISTINCT FROM seq.prev_date THEN 'error' ELSE 'warn' END,
               jsonb_build_object('missing_trading_days', seq.rn - seq.prev_rn - 1,
                                  'previous_bar', seq.prev_date,
                                  'explained_identity_change', i.delisted_on IS NOT DISTINCT FROM seq.prev_date)
        FROM seq LEFT JOIN instruments i USING (symbol)
        WHERE seq.rn - seq.prev_rn - 1 > {TICKER_GAP_DAYS}""",

    "large_move": f"""
        WITH r AS (
            SELECT symbol, trade_date,
                   close * adj_factor / lag(close * adj_factor) OVER (PARTITION BY symbol ORDER BY trade_date) - 1 AS ret
            FROM tradable_bars)
        SELECT symbol, trade_date, 'warn', jsonb_build_object('adjusted_return', round(ret::numeric, 4))
        FROM r WHERE abs(ret) > {LARGE_MOVE}""",
}


@dataclass
class DqReport:
    run_id: uuid.UUID
    counts: dict[tuple[str, str], int] = field(default_factory=dict)

    @property
    def errors(self) -> int:
        return sum(n for (_, sev), n in self.counts.items() if sev == "error")


def _insert(cur: psycopg.Cursor, run_id: uuid.UUID, check: str, rows: list[tuple]) -> None:
    cur.executemany(
        "INSERT INTO data_quality_issues (run_id, check_name, symbol, trade_date, severity, detail) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        [(run_id, check, sym, d, sev, json.dumps(detail) if isinstance(detail, dict) else detail)
         for sym, d, sev, detail in rows])


def run_checks(conn: psycopg.Connection, last_session: date | None) -> DqReport:
    report = DqReport(uuid.uuid4())
    with conn.cursor() as cur:
        for name, sql in CHECKS.items():
            cur.execute(sql)
            rows = cur.fetchall()
            _insert(cur, report.run_id, name, rows)
            for *_, sev, _detail in rows:
                report.counts[(name, sev)] = report.counts.get((name, sev), 0) + 1

        if last_session is not None:
            # Current members that did not really trade in the last completed session.
            cur.execute("""
                WITH current AS (
                    SELECT DISTINCT m.symbol FROM universe_membership m
                    WHERE m.as_of_date = (SELECT max(as_of_date) FROM universe_snapshots s
                                          WHERE s.index_name = m.index_name AND s.as_of_date <= %(d)s))
                SELECT c.symbol, NULL::date, 'warn',
                       jsonb_build_object('last_bar', (SELECT max(trade_date) FROM tradable_bars b
                                                       WHERE b.symbol = c.symbol))
                FROM current c
                WHERE NOT EXISTS (SELECT 1 FROM tradable_bars b WHERE b.symbol = c.symbol AND b.trade_date = %(d)s)""",
                        {"d": last_session})
            rows = cur.fetchall()
            _insert(cur, report.run_id, "stale", rows)
            if rows:
                report.counts[("stale", "warn")] = len(rows)
    return report


def mark_delistings(conn: psycopg.Connection, min_padding: int = TICKER_GAP_DAYS) -> int:
    """Set instruments.delisted_on to the last real session before a long frozen-padding run.

    A symbol with real bars AFTER that run has been reused by another company; `ticker_gap`
    reports it, and `delisted_on` records when the original identity stopped trading.
    """
    with conn.cursor() as cur:
        cur.execute(f"""
            WITH padding AS (
                SELECT b.symbol, count(*) AS sessions, min(b.trade_date) AS from_date
                FROM daily_bars b LEFT JOIN instruments i USING (symbol)
                WHERE b.volume = 0 AND coalesce(i.asset_class, 'us_equity') <> 'index'
                  AND b.open = b.close AND b.high = b.close AND b.low = b.close
                GROUP BY b.symbol, b.close
                HAVING count(*) >= {min_padding}),
            first_run AS (SELECT DISTINCT ON (symbol) symbol, from_date FROM padding ORDER BY symbol, from_date),
            last_real AS (
                SELECT f.symbol, (SELECT max(trade_date) FROM tradable_bars t
                                  WHERE t.symbol = f.symbol AND t.trade_date < f.from_date) AS delisted_on
                FROM first_run f)
            UPDATE instruments i SET delisted_on = l.delisted_on, updated_at = now()
            FROM last_real l
            WHERE i.symbol = l.symbol AND l.delisted_on IS NOT NULL
              AND i.delisted_on IS DISTINCT FROM l.delisted_on""")
        return cur.rowcount


def crosscheck(conn: psycopg.Connection, symbols: list[str], start: date, end: date,
               limiter: SlidingWindowRateLimiter, run_id: uuid.UUID) -> dict[str, int]:
    """Compare Alpaca vs Yahoo *daily returns* (levels differ by each vendor's adjustment base)."""
    disagreements: dict[str, int] = {}
    with conn.cursor() as cur:
        for symbol in symbols:
            cur.execute("SELECT trade_date, close * adj_factor FROM tradable_bars "
                        "WHERE symbol = %s AND source = 'alpaca_sip' AND trade_date BETWEEN %s AND %s "
                        "ORDER BY trade_date", (symbol, start, end))
            ours = dict((d, float(c)) for d, c in cur.fetchall())
            theirs = yahoo.adjusted_closes(symbol.replace(".", "-"), start, end, limiter)
            days = sorted(set(ours) & set(theirs.index))
            if len(days) < 2:
                continue
            a = np.array([ours[d] for d in days])
            y = theirs.loc[days].to_numpy()
            diff = np.abs(a[1:] / a[:-1] - y[1:] / y[:-1])
            bad = [(symbol, days[i + 1], "warn", {"return_diff": round(float(diff[i]), 5)})
                   for i in np.flatnonzero(diff > CROSSCHECK_TOLERANCE)]
            _insert(cur, run_id, "source_disagreement", bad)
            disagreements[symbol] = len(bad)
    return disagreements
