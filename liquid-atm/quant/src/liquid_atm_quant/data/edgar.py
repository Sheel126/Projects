"""SEC EDGAR: ticker<->CIK map and filing indexes with acceptance timestamps (lesson 01 §8)."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

import httpx
import psycopg

from liquid_atm_quant.infra.rate_limiter import SlidingWindowRateLimiter

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{doc}"
FORMS = {"8-K", "8-K/A", "10-Q", "10-K", "4"}


@dataclass(frozen=True)
class Filing:
    accession_no: str
    cik: str
    form: str
    filed_on: date
    accepted_at: datetime
    report_date: date | None
    items: str | None
    primary_document: str | None
    url: str


class Edgar:
    def __init__(self, user_agent: str, limiter: SlidingWindowRateLimiter, http: httpx.Client | None = None) -> None:
        if "@" not in user_agent:
            raise ValueError("SEC requires a User-Agent with a contact email (SEC_USER_AGENT)")
        self._limiter = limiter
        self._http = http or httpx.Client(timeout=30, headers={"User-Agent": user_agent})

    def _get_json(self, url: str) -> dict:
        self._limiter.acquire()
        resp = self._http.get(url)
        resp.raise_for_status()
        return resp.json()

    def company_tickers(self) -> list[tuple[str, str, str]]:
        """(cik10, ticker, title) for every company SEC currently maps to a ticker."""
        data = self._get_json(TICKERS_URL)
        return [(f"{int(r['cik_str']):010d}", r["ticker"].upper(), r["title"]) for r in data.values()]

    def filings(self, cik: str, since: date) -> list[Filing]:
        return parse_submissions(cik, self._get_json(SUBMISSIONS_URL.format(cik=cik)), since)


def parse_submissions(cik: str, body: dict, since: date) -> list[Filing]:
    recent = body.get("filings", {}).get("recent", {})
    out = []
    n = len(recent.get("accessionNumber", []))
    for i in range(n):
        form = recent["form"][i]
        filed_on = date.fromisoformat(recent["filingDate"][i])
        if form not in FORMS or filed_on < since:
            continue
        acc = recent["accessionNumber"][i]
        # acceptanceDateTime is true UTC ("2026-07-30T20:30:28.000Z" = 16:30:28 ET on the index page).
        accepted_at = datetime.fromisoformat(recent["acceptanceDateTime"][i].replace("Z", "+00:00"))
        doc = recent.get("primaryDocument", [None] * n)[i] or None
        report = recent.get("reportDate", [""] * n)[i]
        out.append(Filing(
            accession_no=acc, cik=cik, form=form, filed_on=filed_on,
            accepted_at=accepted_at,
            report_date=date.fromisoformat(report) if report else None,
            items=recent.get("items", [""] * n)[i] or None,
            primary_document=doc,
            url=ARCHIVE_URL.format(cik_int=int(cik), acc_nodash=acc.replace("-", ""), doc=doc or ""),
        ))
    return out


def store_companies(conn: psycopg.Connection, rows: Iterable[tuple[str, str, str]]) -> int:
    rows = list(rows)
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO sec_companies (cik, ticker, title) VALUES (%s, %s, %s)
            ON CONFLICT (cik) DO UPDATE SET ticker = EXCLUDED.ticker, title = EXCLUDED.title, updated_at = now()""",
                        rows)
    return len(rows)


def store_filings(conn: psycopg.Connection, filings: Sequence[Filing]) -> int:
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO sec_filings (accession_no, cik, form, filed_on, accepted_at, report_date, items,
                                     primary_document, url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (accession_no) DO NOTHING""",
                        [(f.accession_no, f.cik, f.form, f.filed_on, f.accepted_at, f.report_date, f.items,
                          f.primary_document, f.url) for f in filings])
    return len(filings)


def ciks_for_symbols(conn: psycopg.Connection, symbols: Sequence[str]) -> dict[str, str]:
    # SEC uses "BRK-B" where Alpaca uses "BRK.B".
    with conn.cursor() as cur:
        cur.execute("SELECT ticker, cik FROM sec_companies WHERE ticker = ANY(%s)",
                    ([s.replace(".", "-") for s in symbols],))
        return {t.replace("-", "."): c for t, c in cur.fetchall()}
