"""Data-layer jobs. All are idempotent and incremental: re-running is always safe.

  python -m liquid_atm_quant.data.cli sync-calendar
  python -m liquid_atm_quant.data.cli sync-assets
  python -m liquid_atm_quant.data.cli universe-live
  python -m liquid_atm_quant.data.cli universe-history
  python -m liquid_atm_quant.data.cli bars [--start 2016-01-04] [--symbols AAPL,MSFT]
  python -m liquid_atm_quant.data.cli yf-backfill
  python -m liquid_atm_quant.data.cli edgar
  python -m liquid_atm_quant.data.cli fundamentals [--start 2014-01-01]   # SEC XBRL company facts
  python -m liquid_atm_quant.data.cli delistings | dq | coverage | crosscheck
  python -m liquid_atm_quant.data.cli daily        # calendar -> universe -> bars -> dq
"""

import argparse
import logging
import random
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import psycopg

from liquid_atm_quant.config import Settings, get_settings
from liquid_atm_quant.data import coverage as cov
from liquid_atm_quant.data import db, edgar, fundamentals, quality, universe, yahoo
from liquid_atm_quant.data.alpaca_data import AlpacaData
from liquid_atm_quant.data.coverage import ALPACA_HISTORY_START
from liquid_atm_quant.infra.rate_limiter import alpaca_limiter, edgar_limiter, yfinance_limiter
from liquid_atm_quant.infra.redis_client import make_redis

log = logging.getLogger("data")

# Benchmarks and regime inputs (lesson 01 §1). ^VIX comes from Yahoo; the rest from Alpaca.
ETFS = ["SPY", "QQQ", "IWM", "DIA", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
        # Cross-asset sleeves for the Phase 3b trend and All-Weather strategies (lesson 03b §4).
        *["TLT", "IEF", "SHY", "TIP", "LQD", "GLD", "DBC", "EFA", "EEM", "VNQ"],
        # Daily-reset 2x/3x S&P 500 and T-bills for the Phase 3c exposure strategies (lesson 03c §4).
        *["SSO", "UPRO", "BIL", "AGG", "VTI"]]
VIX = "^VIX"
YF_HISTORY_START = date(2005, 1, 3)


def _alpaca(settings: Settings) -> AlpacaData:
    if not settings.has_alpaca_keys:
        sys.exit("ALPACA_API_KEY / ALPACA_SECRET_KEY are not set in liquid-atm/.env")
    return AlpacaData(settings.alpaca_api_key, settings.alpaca_secret_key, alpaca_limiter(make_redis(settings)))


def _known_symbols(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT symbol FROM instruments")
        return {r[0] for r in cur.fetchall()}


# ---- jobs ------------------------------------------------------------------------------

def sync_calendar(conn: psycopg.Connection, settings: Settings, start: date = date(2005, 1, 1)) -> None:
    rows = _alpaca(settings).calendar(start, date.today() + timedelta(days=30))
    log.info("calendar sessions upserted: %d", db.upsert_calendar(conn, rows))


def sync_assets(conn: psycopg.Connection, settings: Settings) -> None:
    assets = _alpaca(settings).assets()
    rows = [(a["symbol"], a.get("name"), "etf" if a["symbol"] in ETFS else "us_equity",
             a.get("exchange"), a.get("status") == "active", bool(a.get("tradable")))
            for a in assets]
    rows.append((VIX, "CBOE Volatility Index", "index", "CBOE", True, False))
    log.info("instruments upserted: %d (of which %d active)", db.upsert_instruments(conn, rows),
             sum(1 for r in rows if r[4]))


def universe_live(conn: psycopg.Connection, settings: Settings) -> None:
    with httpx.Client(timeout=60, follow_redirects=True) as http:
        snap = universe.fetch_live_russell1000(http)
    stored, unresolved = universe.store_snapshot(conn, snap, _known_symbols(conn))
    log.info("russell1000 %s: %d members (%d not in Alpaca's asset list: %s)",
             snap.as_of_date, stored, len(unresolved), ",".join(unresolved[:10]))


def universe_history(conn: psycopg.Connection, settings: Settings, since: date = ALPACA_HISTORY_START) -> None:
    known = _known_symbols(conn)
    have = universe.snapshot_dates(conn, universe.RUSSELL_1000)
    with httpx.Client(timeout=120, follow_redirects=True) as http:
        for snap in universe.fetch_wayback_russell1000(http, skip=have):
            stored, _ = universe.store_snapshot(conn, snap, known)
            conn.commit()
            log.info("russell1000 %s (wayback): %d members", snap.as_of_date, stored)
        for snap in universe.fetch_sp500_history(http, since):
            stored, _ = universe.store_snapshot(conn, snap, known)
            log.info("sp500 %s: %d members", snap.as_of_date, stored)


def _symbols_with_bars(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT symbol FROM daily_bars")
        return {r[0] for r in cur.fetchall()}


def bars(conn: psycopg.Connection, settings: Settings, start: date, symbols: list[str] | None,
         only_known: bool = False) -> None:
    api = _alpaca(settings)
    end = db.last_completed_session(conn, datetime.now(UTC))
    if end is None:
        sys.exit("no trading calendar: run sync-calendar first")

    targets = set(symbols or (universe.all_members_since(conn, start) | set(ETFS)))
    if only_known:
        # Daily runs skip historical-only symbols that never returned data (delisted before 2016,
        # renamed, or never on Alpaca); a full `bars` run still retries them.
        current = universe.members_as_of(conn, universe.RUSSELL_1000, end)
        targets &= _symbols_with_bars(conn) | current | set(ETFS)
    targets = sorted(targets)
    last = db.last_bar_dates(conn, targets)
    # Group by resume date so each request batch shares one time window.
    groups: dict[date, list[str]] = {}
    for sym in targets:
        resume = max(start, last[sym] + timedelta(days=1)) if sym in last else start
        if resume <= end:
            groups.setdefault(resume, []).append(sym)

    total = 0
    for resume, syms in sorted(groups.items()):
        for i in range(0, len(syms), 100):
            chunk = syms[i:i + 100]
            rows = api.daily_bars(chunk, resume, end)
            total += db.upsert_bars(conn, rows)
            conn.commit()
            log.info("bars %s..%s: %d symbols -> %d rows (total %d)", resume, end, len(chunk), len(rows), total)
    log.info("bars upserted: %d", total)


def yf_backfill(conn: psycopg.Connection, settings: Settings) -> None:
    """ETF history before Alpaca's 2016 start, plus ^VIX. Never individual stocks (no delisted names)."""
    limiter = yfinance_limiter(make_redis(settings))
    rows = yahoo.daily_bars(ETFS, YF_HISTORY_START, ALPACA_HISTORY_START - timedelta(days=1), limiter)
    rows += yahoo.daily_bars([VIX], YF_HISTORY_START, date.today(), limiter)
    log.info("yfinance bars upserted: %d", db.upsert_bars(conn, rows))


def edgar_sync(conn: psycopg.Connection, settings: Settings, since: date) -> None:
    client = edgar.Edgar(settings.sec_user_agent, edgar_limiter(make_redis(settings)))
    log.info("sec companies upserted: %d", edgar.store_companies(conn, client.company_tickers()))
    conn.commit()
    members = universe.members_as_of(conn, universe.RUSSELL_1000, date.today())
    ciks = edgar.ciks_for_symbols(conn, sorted(members))
    log.info("resolved %d/%d members to CIKs", len(ciks), len(members))
    stored = 0
    for n, (symbol, cik) in enumerate(sorted(ciks.items()), start=1):
        stored += edgar.store_filings(conn, client.filings(cik, since))
        if n % 100 == 0:
            conn.commit()
            log.info("edgar %d/%d symbols, %d filings", n, len(ciks), stored)
    log.info("sec filings stored: %d", stored)


FUNDAMENTALS_ARCHIVE = Path(__file__).resolve().parents[4] / "data" / "cache" / "sec" / "companyfacts.zip"


def fundamentals_sync(conn: psycopg.Connection, settings: Settings, since: date) -> None:
    """Point-in-time fundamentals for every index member since `since` (lesson 03b §2).

    The 1.4 GB archive is downloaded once into data/cache/ (git-ignored); delete it to refresh.
    """
    if not FUNDAMENTALS_ARCHIVE.exists():
        FUNDAMENTALS_ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
        log.info("downloading %s", fundamentals.COMPANYFACTS_URL)
        partial = FUNDAMENTALS_ARCHIVE.with_suffix(".part")
        with httpx.stream("GET", fundamentals.COMPANYFACTS_URL, timeout=600, follow_redirects=True,
                          headers={"User-Agent": settings.sec_user_agent}) as resp:
            resp.raise_for_status()
            with partial.open("wb") as fh:
                for chunk in resp.iter_bytes(1 << 20):
                    fh.write(chunk)
        partial.rename(FUNDAMENTALS_ARCHIVE)
    client = edgar.Edgar(settings.sec_user_agent, edgar_limiter(make_redis(settings)))
    ticker_map = {ticker: cik for cik, ticker, _ in client.company_tickers()}
    stats = fundamentals.sync(conn, FUNDAMENTALS_ARCHIVE, since, ticker_map)
    log.info("fundamentals: %s", stats)


def delistings(conn: psycopg.Connection, settings: Settings) -> None:
    log.info("instruments marked delisted: %d", quality.mark_delistings(conn))


def dq(conn: psycopg.Connection, settings: Settings) -> int:
    report = quality.run_checks(conn, db.last_completed_session(conn, datetime.now(UTC)))
    print(f"\nData-quality run {report.run_id}")
    for (check, severity), count in sorted(report.counts.items()):
        print(f"  {severity:5} {check:20} {count}")
    if not report.counts:
        print("  no issues found")
    print(f"\nerrors: {report.errors} (gate requires 0)")
    return 1 if report.errors else 0


def coverage(conn: psycopg.Connection, settings: Settings) -> None:
    rows = cov.coverage_by_year(conn)
    print(f"\n{'index':12} {'year':>5} {'snaps':>6} {'members':>8} {'covered':>8} {'coverage':>9}")
    for r in rows:
        print(f"{r.index_name:12} {r.year:>5} {r.snapshots:>6} {r.members:>8} {r.covered:>8} {r.ratio:>8.1%}")
    if rows:
        total_members = sum(r.members for r in rows)
        total_covered = sum(r.covered for r in rows)
        print(f"\noverall: {total_covered}/{total_members} = {total_covered / total_members:.1%}")
        print("Phase 4 haircuts backtest returns in proportion to what is missing.")


def crosscheck(conn: psycopg.Connection, settings: Settings, sample: int = 10) -> None:
    members = sorted(universe.members_as_of(conn, universe.RUSSELL_1000, date.today()))
    symbols = ["SPY"] + random.Random(0).sample(members, min(sample, len(members)))
    end = date.today()
    result = quality.crosscheck(conn, symbols, end - timedelta(days=365), end,
                                yfinance_limiter(make_redis(settings)), uuid_run := __import__("uuid").uuid4())
    print(f"\nAlpaca vs Yahoo daily-return crosscheck (run {uuid_run}):")
    for symbol, bad in sorted(result.items()):
        print(f"  {symbol:8} {bad} day(s) differing by more than {quality.CROSSCHECK_TOLERANCE:.1%}")


def daily(conn: psycopg.Connection, settings: Settings) -> int:
    sync_calendar(conn, settings, date.today() - timedelta(days=30))
    universe_live(conn, settings)
    conn.commit()
    bars(conn, settings, ALPACA_HISTORY_START, None, only_known=True)
    delistings(conn, settings)
    return dq(conn, settings)


# ---- entrypoint ------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="liquid-atm-data", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("job", choices=["sync-calendar", "sync-assets", "universe-live", "universe-history",
                                        "bars", "yf-backfill", "edgar", "fundamentals", "delistings", "dq", "coverage",
                                        "crosscheck", "daily"])
    parser.add_argument("--start", type=date.fromisoformat, default=ALPACA_HISTORY_START)
    parser.add_argument("--symbols", help="comma-separated override for the bars job")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    exit_code = 0
    with db.connect(settings) as conn:
        match args.job:
            case "sync-calendar":
                sync_calendar(conn, settings, args.start)
            case "sync-assets":
                sync_assets(conn, settings)
            case "universe-live":
                universe_live(conn, settings)
            case "universe-history":
                universe_history(conn, settings, args.start)
            case "bars":
                bars(conn, settings, args.start, args.symbols.split(",") if args.symbols else None)
            case "yf-backfill":
                yf_backfill(conn, settings)
            case "edgar":
                edgar_sync(conn, settings, args.start)
            case "fundamentals":
                fundamentals_sync(conn, settings, min(args.start, date(2014, 1, 1)))
            case "delistings":
                delistings(conn, settings)
            case "dq":
                exit_code = dq(conn, settings)
            case "coverage":
                coverage(conn, settings)
            case "crosscheck":
                crosscheck(conn, settings)
            case "daily":
                exit_code = daily(conn, settings)
        conn.commit()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
