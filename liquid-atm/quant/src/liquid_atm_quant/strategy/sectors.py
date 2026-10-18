"""Sector labels for the sector cap (lesson 03 §6).

`instruments.sector` holds whatever iShares called the sector in the snapshot it came from, and
iShares changed taxonomy over the years (the older Russell scheme had "Producer Durables",
"Technology", "Telecommunications"). The cap only works if one sector has one name, so labels are
folded onto the 11 GICS-style sectors. Anything unrecognised, blank or "-" becomes "Unknown",
which gets the same cap as every other sector.

Labels are the latest known, not point-in-time: a known, small leak (lesson 03, limitations) that
feeds a diversification cap, never a signal.
"""

import psycopg

GICS = ("Communication", "Consumer Discretionary", "Consumer Staples", "Energy", "Financials",
        "Health Care", "Industrials", "Information Technology", "Materials", "Real Estate",
        "Utilities")

ALIASES = {
    "Communication Services": "Communication",
    "Telecommunications": "Communication",
    "Telecommunication Services": "Communication",
    "Technology": "Information Technology",
    "Financial Services": "Financials",
    "Producer Durables": "Industrials",
    "Autos & Transportation": "Consumer Discretionary",
    "Materials & Processing": "Materials",
    "Other Energy": "Energy",
}

UNKNOWN = "Unknown"


def normalize(label: str | None) -> str:
    if not label:
        return UNKNOWN
    label = label.strip()
    if label in GICS:
        return label
    return ALIASES.get(label, UNKNOWN)


def load_sectors(conn: psycopg.Connection) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT symbol, sector FROM instruments WHERE sector IS NOT NULL")
        return {symbol: normalize(sector) for symbol, sector in cur.fetchall()}
