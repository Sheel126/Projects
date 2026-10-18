"""Integration tests against the Compose Postgres (schema owned by the orchestrator's Flyway).

Every test runs inside a transaction that is rolled back, so the dev database is untouched.
Skipped automatically when the database is not reachable.
"""

from datetime import date, datetime, timezone

import psycopg
import pytest

from liquid_atm_quant.config import get_settings
from liquid_atm_quant.data import coverage as cov
from liquid_atm_quant.data import db, quality, universe
from liquid_atm_quant.data.universe import Holding, Snapshot

SESSIONS = [date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4), date(2026, 3, 5), date(2026, 3, 6)]


@pytest.fixture
def conn():
    settings = get_settings()
    try:
        connection = psycopg.connect(settings.database_url, connect_timeout=3)
    except psycopg.Error as exc:
        pytest.skip(f"database not reachable ({exc}); run `docker compose up -d postgres orchestrator`")
    with connection:
        connection.execute("SET client_min_messages = warning")
        yield connection
        connection.rollback()   # nothing these tests write is kept


def add_calendar(conn, days=SESSIONS):
    db.upsert_calendar(conn, [
        (d, datetime(d.year, d.month, d.day, 14, 30, tzinfo=timezone.utc),
         datetime(d.year, d.month, d.day, 21, 0, tzinfo=timezone.utc), False) for d in days])


def issues_for(conn, run_id, *symbols):
    """Counts of (check, severity) for these symbols only.

    The checks scan whole tables, and the dev database holds millions of real bars, so a test
    must look at the rows it created rather than at global totals.
    """
    rows = conn.execute(
        "SELECT check_name, severity, count(*) FROM data_quality_issues "
        "WHERE run_id = %s AND symbol = ANY(%s) GROUP BY 1, 2", (run_id, list(symbols))).fetchall()
    return {(check, severity): n for check, severity, n in rows}


def add_bars(conn, symbol, days, close=100.0, volume=1_000_000, factor=1.0):
    db.upsert_bars(conn, [db.Bar(symbol, d, close, close + 1, close - 1, close, volume, None, factor, "alpaca_sip")
                          for d in days])


def test_upsert_bars_is_idempotent_and_updates(conn):
    add_bars(conn, "TEST.A", SESSIONS[:2])
    add_bars(conn, "TEST.A", SESSIONS[:2], close=101.0)
    rows = conn.execute("SELECT trade_date, close FROM daily_bars WHERE symbol = 'TEST.A' ORDER BY 1").fetchall()
    assert [(d, float(c)) for d, c in rows] == [(SESSIONS[0], 101.0), (SESSIONS[1], 101.0)]
    assert db.last_bar_dates(conn, ["TEST.A"]) == {"TEST.A": SESSIONS[1]}


def test_last_completed_session_ignores_open_sessions(conn):
    add_calendar(conn)
    midday = datetime(2026, 3, 4, 18, 0, tzinfo=timezone.utc)  # session in progress
    assert db.last_completed_session(conn, midday) == SESSIONS[1]


def test_members_as_of_uses_latest_snapshot_not_the_nearest(conn):
    known = {"OLD.X", "NEW.X"}
    universe.store_snapshot(conn, Snapshot("test_idx", date(2026, 1, 31), "unit",
                                           (Holding("OLD.X", "Old", None, 1.0),)), known)
    universe.store_snapshot(conn, Snapshot("test_idx", date(2026, 6, 30), "unit",
                                           (Holding("NEW.X", "New", None, 1.0),)), known)

    # A date between the two snapshots must see the OLDER one: the June list contains
    # companies added because they had already risen (look-ahead).
    assert universe.members_as_of(conn, "test_idx", date(2026, 5, 1)) == {"OLD.X"}
    assert universe.members_as_of(conn, "test_idx", date(2026, 7, 1)) == {"NEW.X"}
    assert universe.members_as_of(conn, "test_idx", date(2025, 1, 1)) == set()


def test_store_snapshot_replaces_and_reports_unresolved(conn):
    snap = Snapshot("test_idx", date(2026, 2, 2), "unit",
                    (Holding("BRKB", "Berkshire B", "Financials", 1.5), Holding("GONE.X", "Delisted", None, 0.1)))
    stored, unresolved = universe.store_snapshot(conn, snap, {"BRK.B"})
    assert stored == 2
    assert unresolved == ["GONE.X"]                                   # reported...
    assert universe.members_as_of(conn, "test_idx", date(2026, 2, 2)) == {"BRK.B", "GONE.X"}  # ...but kept

    smaller = Snapshot("test_idx", date(2026, 2, 2), "unit", (Holding("BRKB", "Berkshire B", None, 1.5),))
    universe.store_snapshot(conn, smaller, {"BRK.B"})
    assert universe.members_as_of(conn, "test_idx", date(2026, 2, 2)) == {"BRK.B"}  # replaced, not merged


def test_dq_flags_bad_bars_and_member_gaps(conn):
    add_calendar(conn, [date(2026, 1, d) for d in range(2, 31)] + SESSIONS)
    # A member with a long hole in the middle of its history.
    universe.store_snapshot(conn, Snapshot("test_idx", date(2026, 1, 2), "unit",
                                           (Holding("GAP.X", "Gappy", None, 1.0),)), {"GAP.X"})
    add_bars(conn, "GAP.X", [date(2026, 1, 2)])
    add_bars(conn, "GAP.X", SESSIONS)
    # A corrupt bar: low above open.
    db.upsert_bars(conn, [db.Bar("BAD.X", SESSIONS[0], 10.0, 12.0, 11.0, 10.5, 100, None, 1.0, "alpaca_sip")])
    # A legitimate crash: flagged as a warning for review, never deleted.
    add_bars(conn, "CRASH.X", [SESSIONS[0]], close=100.0)
    add_bars(conn, "CRASH.X", [SESSIONS[1]], close=40.0)

    report = quality.run_checks(conn, SESSIONS[-1])
    found = issues_for(conn, report.run_id, "GAP.X", "BAD.X", "CRASH.X")

    assert found.get(("ohlc_sanity", "error")) == 1
    assert found.get(("ticker_gap", "error")) == 1      # inside the universe -> error
    assert found.get(("large_move", "warn")) == 1
    gap = conn.execute(
        "SELECT (detail->>'missing_trading_days')::int FROM data_quality_issues "
        "WHERE run_id = %s AND check_name = 'ticker_gap' AND symbol = 'GAP.X'", (report.run_id,)).fetchone()
    assert gap[0] > quality.TICKER_GAP_DAYS


def test_coverage_counts_members_with_prices(conn):
    add_calendar(conn)
    universe.store_snapshot(conn, Snapshot("test_idx", date(2026, 3, 4), "unit",
                                           (Holding("HAS.X", "Has bars", None, 1.0),
                                            Holding("NONE.X", "No bars", None, 1.0))), set())
    add_bars(conn, "HAS.X", SESSIONS)

    row = next(r for r in cov.coverage_by_year(conn, since=date(2026, 1, 1)) if r.index_name == "test_idx")
    assert (row.members, row.covered) == (2, 1)
    assert row.ratio == 0.5
    assert cov.uncovered_members(conn, "test_idx", date(2026, 3, 4)) == ["NONE.X"]


def add_padding(conn, symbol, days, price=29.05):
    """Alpaca-style post-delisting placeholders: frozen OHLC, zero volume."""
    db.upsert_bars(conn, [db.Bar(symbol, d, price, price, price, price, 0, None, 1.0, "alpaca_sip")
                          for d in days])


def test_frozen_padding_is_detected_and_excluded_from_tradable_bars(conn):
    add_calendar(conn)
    add_bars(conn, "DEAD.X", SESSIONS[:2], close=29.05)
    add_padding(conn, "DEAD.X", SESSIONS[2:])

    found = issues_for(conn, quality.run_checks(conn, SESSIONS[-1]).run_id, "DEAD.X")
    assert found.get(("frozen_padding", "warn")) == 1
    assert found.get(("zero_volume", "warn")) is None   # a run, not isolated halts

    tradable = conn.execute("SELECT count(*) FROM tradable_bars WHERE symbol = 'DEAD.X'").fetchone()[0]
    assert tradable == 2     # the frozen placeholders are not prices anyone could trade


def test_explained_identity_change_is_a_warning_not_an_error(conn):
    jan = [date(2026, 1, d) for d in range(2, 31)]
    add_calendar(conn, jan + SESSIONS)
    universe.store_snapshot(conn, Snapshot("test_idx", date(2026, 1, 2), "unit",
                                           (Holding("REUSE.X", "Reused ticker", None, 1.0),)), {"REUSE.X"})
    add_bars(conn, "REUSE.X", [jan[0]], close=50.0)      # old company's last real session
    add_padding(conn, "REUSE.X", jan[1:], price=50.0)    # frozen while the ticker is dormant
    add_bars(conn, "REUSE.X", SESSIONS, close=12.0)      # a different company, same ticker

    assert quality.mark_delistings(conn, min_padding=20) >= 1
    delisted_on = conn.execute("SELECT delisted_on FROM instruments WHERE symbol = 'REUSE.X'").fetchone()[0]
    assert delisted_on == jan[0]

    found = issues_for(conn, quality.run_checks(conn, SESSIONS[-1]).run_id, "REUSE.X")
    assert found.get(("ticker_gap", "error")) is None    # explained by the recorded delisting
    assert found.get(("ticker_gap", "warn")) == 1


def test_unexplained_hole_in_a_member_is_an_error(conn):
    jan = [date(2026, 1, d) for d in range(2, 31)]
    add_calendar(conn, jan + SESSIONS)
    universe.store_snapshot(conn, Snapshot("test_idx", date(2026, 1, 2), "unit",
                                           (Holding("HOLE.X", "Missing data", None, 1.0),)), {"HOLE.X"})
    add_bars(conn, "HOLE.X", [jan[0]])
    add_bars(conn, "HOLE.X", SESSIONS)   # no padding, no delisting: simply missing data

    found = issues_for(conn, quality.run_checks(conn, SESSIONS[-1]).run_id, "HOLE.X")
    assert found.get(("ticker_gap", "error")) == 1


def test_bar_segments_split_reused_tickers(conn):
    jan = [date(2026, 1, d) for d in range(2, 31)]
    add_calendar(conn, jan + SESSIONS)
    add_bars(conn, "SEG.X", [jan[0]], close=50.0)
    add_bars(conn, "SEG.X", SESSIONS, close=12.0)

    rows = conn.execute("SELECT trade_date, segment_id FROM bar_segments WHERE symbol = 'SEG.X' "
                        "ORDER BY trade_date").fetchall()
    segments = {seg for _, seg in rows}
    assert len(segments) == 2                                  # two identities, never one series
    assert rows[0][1] != rows[-1][1]
