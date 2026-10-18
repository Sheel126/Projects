"""Point-in-time index membership from free sources (see lesson 01 §3).

Sources:
  - iShares IWB live holdings CSV (today's Russell 1000)
  - Wayback Machine captures of the old IWB holdings endpoint (2006-2025, sparse)
  - fja05680/sp500 historical S&P 500 components (dense, exact change dates)
"""

import csv
import io
import json
import logging
import re
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

import httpx
import psycopg

IWB_LIVE_URL = "https://www.ishares.com/us/products/239707/ishares-russell-1000-etf/latest-holdings.csv"
IWB_AJAX_PREFIX = "www.ishares.com/us/products/239707/ishares-russell-1000-etf/1467271812596.ajax"
WAYBACK_CDX = "http://web.archive.org/cdx/search/cdx"
SP500_URL = ("https://raw.githubusercontent.com/fja05680/sp500/master/"
             "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv")
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) liquid-atm research"

log = logging.getLogger(__name__)

RUSSELL_1000 = "russell1000"
SP500 = "sp500"


@dataclass(frozen=True)
class Holding:
    ticker: str
    name: str
    sector: str | None
    weight: float | None


@dataclass(frozen=True)
class Snapshot:
    index_name: str
    as_of_date: date
    source: str
    holdings: tuple[Holding, ...]


# ---- parsing (pure functions, unit-tested) ---------------------------------------------

def _is_equity_ticker(ticker: str, asset_class: str) -> bool:
    # Drop cash, futures, FX and placeholder rows ("-", "USD", "XTSLA" money-market, etc.).
    return asset_class == "Equity" and bool(re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", ticker))


def parse_ishares_csv(text: str) -> tuple[date, list[Holding]]:
    lines = text.lstrip("\ufeff").splitlines()
    as_of = None
    header_idx = None
    for i, line in enumerate(lines[:20]):
        if line.startswith("Fund Holdings as of"):
            as_of = datetime.strptime(next(csv.reader([line]))[1].strip(), "%b %d, %Y").date()
        if line.startswith("Ticker,"):
            header_idx = i
            break
    if as_of is None or header_idx is None:
        raise ValueError("not an iShares holdings CSV")
    holdings = []
    for row in csv.DictReader(io.StringIO("\n".join(lines[header_idx:]))):
        ticker = (row.get("Ticker") or "").strip()
        if not _is_equity_ticker(ticker, (row.get("Asset Class") or "").strip()):
            continue
        weight = row.get("Weight (%)", "").replace(",", "")
        holdings.append(Holding(ticker, row["Name"].strip(), row.get("Sector"),
                                float(weight) if weight not in ("", "-") else None))
    return as_of, holdings


def parse_ishares_json(text: str) -> list[Holding]:
    """Old `.ajax?fileType=json` format: aaData rows [ticker, name, sector, class, mv, weight, ...]."""
    holdings = []
    for row in json.loads(text.lstrip("\ufeff"))["aaData"]:
        ticker, name, sector, asset_class = (str(x).strip() for x in row[:4])
        if not _is_equity_ticker(ticker, asset_class):
            continue
        weight = row[5].get("raw") if isinstance(row[5], dict) else None
        holdings.append(Holding(ticker, name, sector, weight))
    return holdings


def parse_sp500_history(text: str) -> list[tuple[date, list[str]]]:
    out = []
    for row in csv.DictReader(io.StringIO(text.lstrip("\ufeff"))):
        tickers = sorted({t.strip() for t in row["tickers"].split(",") if t.strip()})
        out.append((date.fromisoformat(row["date"]), tickers))
    return out


def wayback_capture_urls(cdx_payload: Sequence[Sequence[str]]) -> dict[date, str]:
    """Pick one archived holdings capture per historical asOfDate (newest capture wins).

    `cdx_payload` is the raw CDX JSON: row 0 is the header naming the columns, so we read
    fields by name rather than assuming their positions.
    """
    header, *rows = cdx_payload
    col = {name: i for i, name in enumerate(header)}
    chosen: dict[date, tuple[str, str]] = {}
    for row in rows:
        timestamp = row[col["timestamp"]]
        original = row[col["original"]]
        mimetype = row[col["mimetype"]]
        m = re.search(r"asOfDate=(\d{8})", original)
        if not m or "tab=all" not in original or mimetype != "application/json":
            continue
        as_of = datetime.strptime(m.group(1), "%Y%m%d").date()
        if as_of not in chosen or timestamp > chosen[as_of][0]:
            chosen[as_of] = (timestamp, original)
    # `id_` asks Wayback for the original bytes, without its HTML toolbar.
    return {d: f"http://web.archive.org/web/{ts}id_/{url}" for d, (ts, url) in chosen.items()}


def resolve_symbol(ticker: str, known: set[str]) -> str | None:
    """Map an index-provider ticker to an Alpaca symbol ("BRKB" -> "BRK.B", "BF.B" stays)."""
    candidates = [ticker, ticker.replace("-", "."), ticker.replace("/", ".")]
    if len(ticker) > 1 and "." not in ticker:
        candidates.append(f"{ticker[:-1]}.{ticker[-1]}")  # share class suffix without a dot
    return next((c for c in candidates if c in known), None)


# ---- fetching --------------------------------------------------------------------------

def fetch_live_russell1000(http: httpx.Client) -> Snapshot:
    resp = http.get(IWB_LIVE_URL, headers={"User-Agent": BROWSER_UA})
    resp.raise_for_status()
    as_of, holdings = parse_ishares_csv(resp.text)
    return Snapshot(RUSSELL_1000, as_of, "ishares_live", tuple(holdings))


def _get_with_retry(http: httpx.Client, url: str, params: dict | None = None,
                    attempts: int = 5, base_delay: float = 5.0) -> httpx.Response:
    """web.archive.org returns 429/503 when busy; back off instead of giving up."""
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            resp = http.get(url, params=params, headers={"User-Agent": BROWSER_UA})
            if resp.status_code in (429, 503, 504):
                raise httpx.HTTPStatusError(f"archive busy: {resp.status_code}",
                                            request=resp.request, response=resp)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPError, httpx.TransportError) as exc:
            last = exc
            log.warning("wayback %s (attempt %d/%d): %s", url[:80], attempt + 1, attempts, exc)
            time.sleep(base_delay * 2 ** attempt)
    raise RuntimeError(f"wayback unavailable after {attempts} attempts: {last}")


def fetch_wayback_russell1000(http: httpx.Client, skip: set[date] = frozenset()) -> Iterable[Snapshot]:
    resp = _get_with_retry(http, WAYBACK_CDX, {"url": IWB_AJAX_PREFIX + "*", "output": "json",
                                               "filter": "statuscode:200", "limit": 5000})
    for as_of, url in sorted(wayback_capture_urls(resp.json()).items()):
        if as_of in skip:
            continue
        try:
            snap = _get_with_retry(http, url)
            holdings = tuple(parse_ishares_json(snap.text))
        except (RuntimeError, ValueError, KeyError) as exc:
            # One unreadable capture must not abort the whole history import.
            log.warning("skipping wayback snapshot %s: %s", as_of, exc)
            continue
        yield Snapshot(RUSSELL_1000, as_of, "ishares_wayback", holdings)


def fetch_sp500_history(http: httpx.Client, since: date) -> list[Snapshot]:
    resp = http.get(SP500_URL)
    resp.raise_for_status()
    return [Snapshot(SP500, d, "fja05680_sp500", tuple(Holding(t, t, None, None) for t in tickers))
            for d, tickers in parse_sp500_history(resp.text) if d >= since]


# ---- storage & point-in-time queries ---------------------------------------------------

def store_snapshot(conn: psycopg.Connection, snap: Snapshot, known_symbols: set[str]) -> tuple[int, list[str]]:
    """Replace one snapshot. Returns (stored count, tickers not found in Alpaca's asset list).

    Unresolved tickers are still stored as-is: Alpaca often has bars for delisted symbols it no
    longer lists as assets. Whether prices exist is what the coverage report measures.
    """
    resolved: dict[str, Holding] = {}
    unresolved = []
    for h in snap.holdings:
        sym = resolve_symbol(h.ticker, known_symbols)
        if sym is None:
            unresolved.append(h.ticker)
            sym = h.ticker
        resolved[sym] = h
    with conn.cursor() as cur:
        cur.execute("DELETE FROM universe_membership WHERE index_name = %s AND as_of_date = %s",
                    (snap.index_name, snap.as_of_date))
        cur.executemany(
            "INSERT INTO universe_membership (index_name, as_of_date, symbol, weight, source) "
            "VALUES (%s, %s, %s, %s, %s)",
            [(snap.index_name, snap.as_of_date, s, h.weight, snap.source) for s, h in resolved.items()])
        cur.execute("""
            INSERT INTO universe_snapshots (index_name, as_of_date, source, member_count)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (index_name, as_of_date) DO UPDATE SET
                source = EXCLUDED.source, member_count = EXCLUDED.member_count, fetched_at = now()""",
                    (snap.index_name, snap.as_of_date, snap.source, len(resolved)))
        cur.executemany(
            "INSERT INTO instruments (symbol, name, asset_class, is_active) VALUES (%s, %s, 'us_equity', FALSE) "
            "ON CONFLICT (symbol) DO NOTHING",
            [(s, h.name) for s, h in resolved.items()])
        # Sector is descriptive metadata; keep the latest known value.
        cur.executemany("UPDATE instruments SET sector = %s WHERE symbol = %s",
                        [(h.sector, s) for s, h in resolved.items() if h.sector])
    return len(resolved), unresolved


def snapshot_dates(conn: psycopg.Connection, index_name: str) -> set[date]:
    with conn.cursor() as cur:
        cur.execute("SELECT as_of_date FROM universe_snapshots WHERE index_name = %s", (index_name,))
        return {r[0] for r in cur.fetchall()}


def members_as_of(conn: psycopg.Connection, index_name: str, when: date) -> set[str]:
    """Members from the latest snapshot that EXISTED on `when`: never a later, 'closer' one."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT m.symbol FROM universe_membership m
            WHERE m.index_name = %(idx)s
              AND m.as_of_date = (SELECT max(as_of_date) FROM universe_snapshots
                                  WHERE index_name = %(idx)s AND as_of_date <= %(when)s)""",
                    {"idx": index_name, "when": when})
        return {r[0] for r in cur.fetchall()}


def all_members_since(conn: psycopg.Connection, since: date) -> set[str]:
    """Every symbol that was in any index at any snapshot in force since `since` (ingestion scope)."""
    with conn.cursor() as cur:
        cur.execute("""
            WITH in_force AS (   -- per index, the snapshot that was current on `since`
                SELECT index_name, max(as_of_date) AS as_of_date FROM universe_snapshots
                WHERE as_of_date <= %(since)s GROUP BY index_name)
            SELECT DISTINCT m.symbol FROM universe_membership m
            LEFT JOIN in_force f USING (index_name)
            WHERE m.as_of_date >= coalesce(f.as_of_date, %(since)s)""",
                    {"since": since})
        return {r[0] for r in cur.fetchall()}
