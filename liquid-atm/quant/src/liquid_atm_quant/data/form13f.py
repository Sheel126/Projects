"""SEC Form 13F Data Sets: institutional holdings since 2013 Q3 (lesson 03d §7).

Each ZIP holds a quarter of filings, flattened into SUBMISSION (accession, filing date, CIK,
period), COVERPAGE (amendment flags, manager name) and INFOTABLE (one row per holding: CUSIP,
VALUE, SSHPRNAMT, PUTCALL). VALUE is in thousands of dollars before 3 January 2023 and in dollars
after; `load` puts everything in dollars.

**CUSIPs without a CUSIP database.** CUSIP-to-ticker maps are sold, not given away. We do not need
one: a 13F reports both the value and the share count of every holding, so it reveals the price
the filer marked it at on the period-end date. A CUSIP is matched to the index member whose close
that day is within 1% of the implied price *and* whose name shares a word with the filer's
`NAMEOFISSUER`. Two independent facts agreeing is a stricter test than either alone, and a holding
that matches nothing is simply left out (and its share of the filer's book is reported).
"""

import csv
import io
import logging
import re
import zipfile
from datetime import date, datetime
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

log = logging.getLogger("data.form13f")

BASE = "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"
CACHE = Path(__file__).resolve().parents[4] / "data" / "cache" / "form13f"
HOLDINGS = CACHE / "holdings.csv.gz"
VALUE_IN_DOLLARS_FROM = date(2023, 1, 3)
STOPWORDS = {"INC", "CORP", "CO", "COM", "LTD", "PLC", "THE", "GROUP", "HLDGS", "HOLDINGS", "CL",
             "A", "B", "NEW", "DEL", "CORPORATION", "COMPANY", "INCORPORATED", "LP", "N", "V",
             "SA", "AG", "NV", "TR", "TRUST", "SHS", "ORD", "CLASS", "&", "OF", "AND", "DE"}


def files(last_quarter: tuple[int, int] = (2023, 4)) -> list[str]:
    """2013 Q3 through 2023 Q4 quarterly, then the 2024 three-month bundles that end before the
    lockbox. (The Sep-Nov 2024 bundle holds lockbox filings and is never fetched.)"""
    out = []
    year, quarter = 2013, 3
    while (year, quarter) <= last_quarter:
        out.append(f"{year}q{quarter}_form13f.zip")
        year, quarter = (year + 1, 1) if quarter == 4 else (year, quarter + 1)
    out += ["01jan2024-29feb2024_form13f.zip", "01mar2024-31may2024_form13f.zip",
            "01jun2024-31aug2024_form13f.zip"]
    return out


def download(http: httpx.Client, limiter, names: list[str]) -> None:
    for name in names:
        path = CACHE / "zips" / name
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        limiter.acquire()
        resp = http.get(BASE + name)
        resp.raise_for_status()
        path.write_bytes(resp.content)
        log.info("%s: %.1f MB", name, len(resp.content) / 1e6)


def _rows(archive: zipfile.ZipFile, table: str):
    member = next(n for n in archive.namelist() if n.upper().endswith(f"{table}.TSV"))
    with archive.open(member) as fh:
        yield from csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"),
                                  delimiter="\t", quoting=csv.QUOTE_NONE)


def _date(text: str) -> date | None:
    try:
        return datetime.strptime(text.strip(), "%d-%b-%Y").date()
    except (AttributeError, ValueError):
        return None


def parse(path: Path, max_positions: int) -> list[tuple]:
    """Holdings of original (non-amendment) 13F-HR filings with at most `max_positions` share
    lines. Big index-like books are dropped here: they are not anyone's best ideas, and they are
    most of the file."""
    with zipfile.ZipFile(path) as archive:
        subs = {}
        for r in _rows(archive, "SUBMISSION"):
            if r.get("SUBMISSIONTYPE", "").strip() == "13F-HR":
                subs[r["ACCESSION_NUMBER"]] = (_date(r["FILING_DATE"]), r["CIK"].strip(),
                                               _date(r["PERIODOFREPORT"]))
        for r in _rows(archive, "COVERPAGE"):
            if (r.get("ISAMENDMENT") or "").strip().upper() in ("Y", "TRUE", "1"):
                subs.pop(r["ACCESSION_NUMBER"], None)
        lines: dict[str, list[tuple]] = {}
        for r in _rows(archive, "INFOTABLE"):
            acc = r["ACCESSION_NUMBER"]
            if acc not in subs or (r.get("PUTCALL") or "").strip():
                continue
            if (r.get("SSHPRNAMTTYPE") or "").strip().upper() != "SH":
                continue
            try:
                value, shares = float(r["VALUE"]), float(r["SSHPRNAMT"])
            except (TypeError, ValueError):
                continue
            lines.setdefault(acc, []).append((r["CUSIP"].strip().upper(),
                                              r["NAMEOFISSUER"].strip().upper(), value, shares))
    out = []
    for acc, holdings in lines.items():
        filed, cik, period = subs[acc]
        if filed is None or period is None:
            continue
        # One CUSIP can appear on several lines (sub-advisers, voting classes): merge them.
        merged: dict[str, list] = {}
        for cusip, name, value, shares in holdings:
            row = merged.setdefault(cusip, [name, 0.0, 0.0])
            row[1] += value
            row[2] += shares
        if len(merged) > max_positions:
            continue
        scale = 1.0 if filed >= VALUE_IN_DOLLARS_FROM else 1000.0
        for cusip, (name, value, shares) in merged.items():
            out.append((acc, filed, cik, period, cusip, name, value * scale, shares))
    return out


def build(names: list[str], max_positions: int) -> pd.DataFrame:
    rows = []
    for name in names:
        part = parse(CACHE / "zips" / name, max_positions)
        log.info("%s: %d holdings rows", name, len(part))
        rows.extend(part)
    frame = pd.DataFrame(rows, columns=["accession", "filing_date", "cik", "period", "cusip",
                                        "issuer", "value", "shares"]).drop_duplicates()
    frame.to_csv(HOLDINGS, index=False, compression="gzip")
    return frame


def load(path: Path = HOLDINGS) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"cik": str, "cusip": str, "accession": str},
                        parse_dates=["filing_date", "period"])
    frame["filing_date"] = frame["filing_date"].dt.date
    frame["period"] = frame["period"].dt.date
    return frame


def name_words(name: str) -> set[str]:
    return {w for w in re.split(r"[^A-Z0-9]+", (name or "").upper()) if w and w not in STOPWORDS}


def match_cusips(holdings: pd.DataFrame, closes: dict[date, dict[str, float]],
                 names: dict[str, str], tolerance: float = 0.01) -> dict[str, str]:
    """CUSIP -> symbol, by implied price plus a shared name word (see the module docstring).

    The first period that yields exactly one match decides; later periods only fill CUSIPs
    still unmatched. `closes` is {period-end session: {symbol: raw close}}."""
    words = {s: name_words(n) for s, n in names.items()}
    out: dict[str, str] = {}
    lines = holdings[holdings["shares"] > 0].drop_duplicates(["cusip", "period"])
    for period, g in lines.groupby("period", sort=True):
        day_closes = closes.get(period)
        if not day_closes:
            continue
        symbols = np.array(list(day_closes))
        prices = np.array([day_closes[s] for s in symbols])
        order = np.argsort(prices)
        symbols, prices = symbols[order], prices[order]
        for cusip, issuer, value, shares in zip(g["cusip"], g["issuer"], g["value"], g["shares"]):
            if cusip in out:
                continue
            implied = value / shares
            lo = np.searchsorted(prices, implied / (1 + tolerance))
            hi = np.searchsorted(prices, implied / (1 - tolerance), side="right")
            if lo >= hi:
                continue
            issuer_words = name_words(issuer)
            hits = [s for s in symbols[lo:hi] if issuer_words & words.get(s, set())]
            if len(hits) == 1:
                out[cusip] = str(hits[0])
    return out


__all__ = ["CACHE", "HOLDINGS", "build", "download", "files", "load", "match_cusips",
           "name_words", "parse"]
