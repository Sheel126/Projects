"""Postgres access for the data layer.

Functions take an open connection and never commit: the caller (CLI job or test) owns the
transaction, so a failed job leaves nothing half-written and tests can roll back.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

import psycopg

from liquid_atm_quant.config import Settings


def connect(settings: Settings) -> psycopg.Connection:
    return psycopg.connect(settings.database_url)


@dataclass(frozen=True)
class Bar:
    symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None
    adj_factor: float
    source: str


def upsert_bars(conn: psycopg.Connection, bars: Iterable[Bar]) -> int:
    """Bulk upsert via COPY into a temp table (fast), then one INSERT ... ON CONFLICT."""
    rows = list(bars)
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TEMP TABLE IF NOT EXISTS _bars_in
            (LIKE daily_bars INCLUDING DEFAULTS) ON COMMIT DROP""")
        cur.execute("TRUNCATE _bars_in")
        with cur.copy("COPY _bars_in (symbol, trade_date, open, high, low, close, volume, vwap, "
                      "adj_factor, source) FROM STDIN") as copy:
            for b in rows:
                copy.write_row((b.symbol, b.trade_date, b.open, b.high, b.low, b.close,
                                b.volume, b.vwap, b.adj_factor, b.source))
        cur.execute("""
            INSERT INTO daily_bars (symbol, trade_date, open, high, low, close, volume, vwap,
                                    adj_factor, source)
            SELECT symbol, trade_date, open, high, low, close, volume, vwap, adj_factor, source
            FROM _bars_in
            ON CONFLICT (symbol, trade_date) DO UPDATE SET
                open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                close = EXCLUDED.close, volume = EXCLUDED.volume, vwap = EXCLUDED.vwap,
                adj_factor = EXCLUDED.adj_factor, source = EXCLUDED.source, ingested_at = now()""")
    return len(rows)


def last_bar_dates(conn: psycopg.Connection, symbols: Sequence[str]) -> dict[str, date]:
    with conn.cursor() as cur:
        cur.execute("SELECT symbol, max(trade_date) FROM daily_bars WHERE symbol = ANY(%s) GROUP BY symbol",
                    (list(symbols),))
        return {s: d for s, d in cur.fetchall()}


def upsert_instruments(conn: psycopg.Connection, rows: Iterable[tuple]) -> int:
    """rows: (symbol, name, asset_class, exchange, is_active, tradable)."""
    rows = list(rows)
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO instruments (symbol, name, asset_class, exchange, is_active, tradable)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol) DO UPDATE SET
                name = EXCLUDED.name, exchange = EXCLUDED.exchange, is_active = EXCLUDED.is_active,
                tradable = EXCLUDED.tradable, updated_at = now(),
                -- never downgrade an ETF/index classification we set deliberately
                asset_class = CASE WHEN instruments.asset_class = 'us_equity'
                                   THEN EXCLUDED.asset_class ELSE instruments.asset_class END""",
                        rows)
    return len(rows)


def upsert_calendar(conn: psycopg.Connection, rows: Iterable[tuple[date, datetime, datetime, bool]]) -> int:
    rows = list(rows)
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO trading_calendar (trade_date, session_open, session_close, is_early_close)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (trade_date) DO UPDATE SET session_open = EXCLUDED.session_open,
                session_close = EXCLUDED.session_close, is_early_close = EXCLUDED.is_early_close""",
                        rows)
    return len(rows)


def last_completed_session(conn: psycopg.Connection, now: datetime) -> date | None:
    with conn.cursor() as cur:
        cur.execute("SELECT max(trade_date) FROM trading_calendar WHERE session_close <= %s", (now,))
        return cur.fetchone()[0]
