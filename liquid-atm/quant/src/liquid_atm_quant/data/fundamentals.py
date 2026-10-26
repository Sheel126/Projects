"""SEC XBRL company facts -> point-in-time fundamentals (lesson 03b §2).

Source: SEC's nightly bulk archive `companyfacts.zip` (one JSON per company, every XBRL fact the
company ever filed in a 10-K or 10-Q, each with the date it was filed). Free, no key, 2009 on.

Three rules turn that archive into something a backtest may read:

1. **First report wins.** Every 10-K repeats last year's numbers and restatements rewrite old
   ones. For each (company, concept, period) we keep the value from the earliest filing, because
   that is the only one the market could have read at the time.
2. **One concept, many tags.** Companies switched tags over the years (revenue moved to
   `RevenueFromContractWithCustomer...` under ASC 606 in 2018). `CONCEPTS` lists the aliases for
   each normalized concept; across aliases the earliest filing still wins, ties go to the first
   alias listed.
3. **Symbols are tied to CIKs carefully.** SEC's ticker map is current-only, so a delisted company
   is found by matching Alpaca's company name to the XBRL entity name instead. Ticker reuse is
   guarded at read time (`backtest/fundamentals.py`), not here.
"""

import json
import logging
import re
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import psycopg

log = logging.getLogger("data.fundamentals")

COMPANYFACTS_URL = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"

# normalized concept -> (unit, aliases in priority order). "dei:" tags live in the cover-page
# taxonomy; everything else is us-gaap.
CONCEPTS: dict[str, tuple[str, tuple[str, ...]]] = {
    # ---- income statement and cash flow (durations) ----
    "revenue": ("USD", ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                        "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax",
                        "SalesRevenueGoodsNet", "RevenuesNetOfInterestExpense")),
    "gross_profit": ("USD", ("GrossProfit",)),
    "operating_income": ("USD", ("OperatingIncomeLoss",)),
    "net_income": ("USD", ("NetIncomeLoss", "ProfitLoss",
                           "NetIncomeLossAvailableToCommonStockholdersBasic")),
    "cfo": ("USD", ("NetCashProvidedByUsedInOperatingActivities",
                    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations")),
    "capex": ("USD", ("PaymentsToAcquirePropertyPlantAndEquipment",
                      "PaymentsToAcquireProductiveAssets")),
    "eps_diluted": ("USD/shares", ("EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted",
                                   "EarningsPerShareBasic")),
    # ---- balance sheet (instants) ----
    "assets": ("USD", ("Assets",)),
    "current_assets": ("USD", ("AssetsCurrent",)),
    "current_liabilities": ("USD", ("LiabilitiesCurrent",)),
    "cash": ("USD", ("CashAndCashEquivalentsAtCarryingValue",
                     "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "Cash")),
    "equity": ("USD", ("StockholdersEquity",
                       "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest")),
    "lt_debt": ("USD", ("LongTermDebtNoncurrent", "LongTermDebt",
                        "LongTermDebtAndCapitalLeaseObligations",
                        "LongTermDebtAndFinanceLeaseObligationsNoncurrent")),
    "st_debt": ("USD", ("DebtCurrent", "LongTermDebtCurrent", "ShortTermBorrowings")),
    "ppe_net": ("USD", ("PropertyPlantAndEquipmentNet",)),
    "shares_out": ("shares", ("dei:EntityCommonStockSharesOutstanding",
                              "CommonStockSharesOutstanding")),
}

DURATION = {"revenue", "gross_profit", "operating_income", "net_income", "cfo", "capex",
            "eps_diluted"}

FORMS = ("10-K", "10-Q", "10-K/A", "10-Q/A", "10-KT", "20-F", "40-F")


@dataclass(frozen=True)
class Fact:
    cik: str
    concept: str
    period_start: date | None
    period_end: date
    value: float
    filed: date
    form: str
    accn: str
    source_tag: str


def parse_company(body: dict) -> list[Fact]:
    """Every first-reported fact for one company, normalized onto `CONCEPTS`."""
    cik = f"{int(body['cik']):010d}"
    taxonomies = body.get("facts", {})
    out: list[Fact] = []
    for concept, (unit, aliases) in CONCEPTS.items():
        best: dict[tuple[date | None, date], tuple[tuple[date, int], Fact]] = {}
        for priority, alias in enumerate(aliases):
            taxonomy, tag = alias.split(":", 1) if ":" in alias else ("us-gaap", alias)
            entries = taxonomies.get(taxonomy, {}).get(tag, {}).get("units", {}).get(unit, [])
            for e in entries:
                form = e.get("form", "")
                if not form.startswith(FORMS) or "end" not in e or "filed" not in e:
                    continue
                start = date.fromisoformat(e["start"]) if "start" in e else None
                if (concept in DURATION) != (start is not None):
                    continue            # a duration concept reported as an instant, or vice versa
                fact = Fact(cik, concept, start, date.fromisoformat(e["end"]), float(e["val"]),
                            date.fromisoformat(e["filed"]), form, e.get("accn", ""), tag)
                key = (fact.period_start, fact.period_end)
                rank = (fact.filed, priority)
                if key not in best or rank < best[key][0]:
                    best[key] = (rank, fact)
        out.extend(fact for _, fact in best.values())
    return out


# ---- symbol -> CIK -------------------------------------------------------------------------

_SUFFIXES = re.compile(
    r"\b(the|inc|incorporated|corp|corporation|co|company|companies|ltd|limited|plc|llc|lp|l p|"
    r"sa|nv|ag|se|holdings?|group|common stock|capital stock|class [a-c]|ordinary shares?|"
    r"american depositary shares?|ads|new|del|de)\b")


def normalize_name(name: str | None) -> str:
    """'Apple Inc. Common Stock', 'APPLE INC' -> 'apple'; 'ExxonMobil' and 'Exxon Mobil' agree."""
    if not name:
        return ""
    text = re.sub(r"[^a-z0-9 ]", " ", name.lower().replace("&", " and "))
    text = _SUFFIXES.sub(" ", text)
    return "".join(text.split())


_HEAD = re.compile(rb'"cik"\s*:\s*(\d+).*?"entityName"\s*:\s*"((?:[^"\\]|\\.)*)"', re.S)


def entity_names(archive: zipfile.ZipFile) -> dict[str, str]:
    """{cik: entityName} for every company in the archive, reading only each file's first bytes."""
    out: dict[str, str] = {}
    for name in archive.namelist():
        with archive.open(name) as fh:
            head = fh.read(600)
        match = _HEAD.search(head)
        if match:
            out[f"{int(match.group(1)):010d}"] = json.loads(b'"' + match.group(2) + b'"')
    return out


def candidate_ciks(symbols: dict[str, str | None], ticker_map: dict[str, str],
                   names: dict[str, str]) -> dict[str, list[tuple[str, str]]]:
    """{symbol: [(cik, source), ...]} from SEC's ticker map and a unique normalized-name match.

    Both are kept because each fails differently: the ticker map is current-only (a reused ticker
    points at the new company, a holding-company reorganisation at a CIK with no history), and the
    name match misses renamed companies. `sync` keeps whichever has more reported history.
    """
    by_name: dict[str, set[str]] = {}
    for cik, entity in names.items():
        key = normalize_name(entity)
        if key:
            by_name.setdefault(key, set()).add(cik)
    out: dict[str, list[tuple[str, str]]] = {}
    for symbol, name in symbols.items():
        found: list[tuple[str, str]] = []
        cik = ticker_map.get(symbol) or ticker_map.get(symbol.replace(".", "-"))
        if cik and cik in names:
            found.append((cik, "ticker"))
        matches = by_name.get(normalize_name(name), set())
        if len(matches) == 1 and next(iter(matches)) not in {c for c, _ in found}:
            found.append((next(iter(matches)), "name"))
        if found:
            out[symbol] = found
    return out


def choose(candidates: dict[str, list[tuple[str, str]]],
           history: dict[str, int]) -> dict[str, tuple[str, str]]:
    """Per symbol, the candidate CIK with the most reported quarters (ties: ticker map first)."""
    out = {}
    for symbol, options in candidates.items():
        best = max(options, key=lambda option: history.get(option[0], 0))
        if history.get(best[0], 0) > 0:
            out[symbol] = best
    return out


# ---- storage -------------------------------------------------------------------------------

def iter_facts(archive: zipfile.ZipFile, ciks: Iterable[str]) -> Iterator[Fact]:
    available = set(archive.namelist())
    for cik in sorted(set(ciks)):
        member = f"CIK{cik}.json"
        if member in available:
            yield from parse_company(json.loads(archive.read(member)))


def store_facts(conn: psycopg.Connection, ciks: set[str], facts: Iterable[Fact]) -> int:
    """Replace every stored fact for `ciks`. Rebuilding is idempotent; there is nothing to merge."""
    n = 0
    with conn.cursor() as cur:
        cur.execute("DELETE FROM fundamental_facts WHERE cik = ANY(%s)", (sorted(ciks),))
        with cur.copy("COPY fundamental_facts (cik, concept, period_start, period_end, value, "
                      "filed, form, accn, source_tag) FROM STDIN") as copy:
            for f in facts:
                copy.write_row((f.cik, f.concept, f.period_start, f.period_end, f.value, f.filed,
                                f.form, f.accn, f.source_tag))
                n += 1
    return n


def sync(conn: psycopg.Connection, archive_path: Path, since: date,
         ticker_map: dict[str, str]) -> dict[str, int]:
    """Resolve every index member since `since` to a CIK and load its first-reported facts.

    `ticker_map` is SEC's full current list (every share class: GOOG, GOOGL and GOOGN all map to
    Alphabet); `sec_companies` keeps one ticker per CIK, which is not enough here.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT m.symbol, i.name
            FROM universe_membership m LEFT JOIN instruments i ON i.symbol = m.symbol
            WHERE m.as_of_date >= %s""", (since,))
        symbols = dict(cur.fetchall())

    with zipfile.ZipFile(archive_path) as archive:
        names = entity_names(archive)
        candidates = candidate_ciks(symbols, ticker_map, names)
        facts: dict[str, list[Fact]] = {}
        for cik in {c for options in candidates.values() for c, _ in options}:
            facts[cik] = list(iter_facts(archive, [cik]))
    history = {cik: sum(1 for f in rows if f.concept in ("net_income", "revenue"))
               for cik, rows in facts.items()}
    resolved = choose(candidates, history)
    log.info("resolved %d/%d symbols (%d by ticker, %d by name)", len(resolved), len(symbols),
             sum(1 for _, s in resolved.values() if s == "ticker"),
             sum(1 for _, s in resolved.values() if s == "name"))
    ciks = {cik for cik, _ in resolved.values()}
    stored = store_facts(conn, set(facts), (f for cik in sorted(ciks) for f in facts[cik]))

    with conn.cursor() as cur:
        cur.execute("UPDATE instruments SET cik = NULL, cik_source = NULL "
                    "WHERE cik_source IS NOT NULL")
        cur.executemany("UPDATE instruments SET cik = %s, cik_source = %s, updated_at = now() "
                        "WHERE symbol = %s",
                        [(cik, source, symbol) for symbol, (cik, source) in resolved.items()])
    return {"symbols": len(symbols), "resolved": len(resolved), "ciks": len(ciks), "facts": stored}
