"""SEC Insider Transactions Data Sets: every Form 3/4/5 since 2006, as quarterly ZIPs (lesson 03d §6).

The SEC flattens each quarter's filings into tab-separated tables. Three of them are enough:

* `SUBMISSION`      one row per filing: accession, FILING_DATE, ISSUERCIK, DOCUMENT_TYPE
* `REPORTINGOWNER`  who filed: RPTOWNERCIK and RPTOWNER_RELATIONSHIP (director, officer, ...)
* `NONDERIV_TRANS`  the trades: TRANS_DATE, TRANS_CODE (P = open-market purchase, S = sale),
                    TRANS_SHARES, TRANS_PRICEPERSHARE, TRANS_ACQUIRED_DISP_CD

Only open-market trades (codes P and S) are kept: grants, option exercises and gifts are
compensation, not opinions. Sales are kept because classifying an insider as *routine* (Cohen,
Malloy & Pomorski) needs their whole trading history, sales included.

**The date that matters is FILING_DATE**, not the trade date: an insider has two business days to
file, and nobody outside knew about the trade until the filing was public. The strategy acts the
session after the filing date, which is late by up to a day for a morning filing and never early.
"""

import csv
import io
import logging
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import httpx
import pandas as pd

log = logging.getLogger("data.insiders")

URL = ("https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/"
       "{year}q{quarter}_form345.zip")
CACHE = Path(__file__).resolve().parents[4] / "data" / "cache" / "insiders"
TRADES = CACHE / "open_market_trades.csv.gz"
COLUMNS = ["accession", "filing_date", "issuer_cik", "issuer_symbol", "owner_cik",
           "relationship", "title", "trans_date", "code", "shares", "price"]


@dataclass(frozen=True)
class Quarter:
    year: int
    quarter: int

    @property
    def url(self) -> str:
        return URL.format(year=self.year, quarter=self.quarter)

    @property
    def path(self) -> Path:
        return CACHE / "zips" / f"{self.year}q{self.quarter}_form345.zip"


def quarters(first: Quarter, last: Quarter) -> list[Quarter]:
    out, y, q = [], first.year, first.quarter
    while (y, q) <= (last.year, last.quarter):
        out.append(Quarter(y, q))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def download(http: httpx.Client, limiter, qs: list[Quarter]) -> None:
    for q in qs:
        if q.path.exists():
            continue
        q.path.parent.mkdir(parents=True, exist_ok=True)
        limiter.acquire()
        resp = http.get(q.url)
        resp.raise_for_status()
        q.path.write_bytes(resp.content)
        log.info("%s: %.1f MB", q.path.name, len(resp.content) / 1e6)


def _table(archive: zipfile.ZipFile, name: str) -> list[dict]:
    member = next(n for n in archive.namelist() if n.upper().endswith(f"{name}.TSV"))
    with archive.open(member) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace")
        return list(csv.DictReader(text, delimiter="\t", quoting=csv.QUOTE_NONE))


def _date(text: str) -> date | None:
    text = (text or "").strip()
    for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _float(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_quarter(path: Path) -> list[tuple]:
    """Open-market trades (P/S) on Forms 4 and 4/A from one quarterly ZIP."""
    with zipfile.ZipFile(path) as archive:
        subs = {r["ACCESSION_NUMBER"]: r for r in _table(archive, "SUBMISSION")
                if r.get("DOCUMENT_TYPE", "").strip() in ("4", "4/A")}
        owners: dict[str, list[dict]] = {}
        for r in _table(archive, "REPORTINGOWNER"):
            if r["ACCESSION_NUMBER"] in subs:
                owners.setdefault(r["ACCESSION_NUMBER"], []).append(r)
        rows = []
        for r in _table(archive, "NONDERIV_TRANS"):
            acc = r["ACCESSION_NUMBER"]
            code = (r.get("TRANS_CODE") or "").strip()
            sub = subs.get(acc)
            if sub is None or code not in ("P", "S"):
                continue
            filed, traded = _date(sub["FILING_DATE"]), _date(r.get("TRANS_DATE", ""))
            shares, price = _float(r.get("TRANS_SHARES")), _float(r.get("TRANS_PRICEPERSHARE"))
            if filed is None or shares is None:
                continue
            # A joint filing names several owners; each is credited with the trade, which is
            # what the cluster count needs (distinct people) - their value is not summed twice
            # because value is only used per owner.
            for owner in owners.get(acc, []):
                rows.append((acc, filed, sub["ISSUERCIK"].strip().zfill(10),
                             sub.get("ISSUERTRADINGSYMBOL", "").strip().upper(),
                             owner["RPTOWNERCIK"].strip().zfill(10),
                             (owner.get("RPTOWNER_RELATIONSHIP") or "").upper(),
                             (owner.get("RPTOWNER_TITLE") or "").strip(),
                             traded, code, shares, price))
    return rows


def build(qs: list[Quarter]) -> pd.DataFrame:
    rows = []
    for q in qs:
        part = parse_quarter(q.path)
        log.info("%s: %d open-market rows", q.path.name, len(part))
        rows.extend(part)
    frame = pd.DataFrame(rows, columns=COLUMNS).drop_duplicates()
    TRADES.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TRADES, index=False, compression="gzip")
    return frame


def load(path: Path = TRADES) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"issuer_cik": str, "owner_cik": str, "accession": str},
                        parse_dates=["filing_date", "trans_date"])
    frame["filing_date"] = frame["filing_date"].dt.date
    frame["trans_date"] = frame["trans_date"].dt.date
    return frame


__all__ = ["CACHE", "Quarter", "TRADES", "build", "download", "load", "parse_quarter",
           "quarters"]
