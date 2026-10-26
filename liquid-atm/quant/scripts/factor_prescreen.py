"""The free pre-screen (lesson 03b §1): did each investor style's underlying factor pay, in BIG
US stocks, over our in-sample window?

Uses Ken French's data library (free, CRSP-based, survivorship-free - better data than ours) and
the 2x3 size sorts, keeping only the BIG half: our universe is the Russell 1000, and most published
anomalies are much weaker among large caps than in the small stocks that dominate equal-weighted
results.

    python scripts/factor_prescreen.py               # in-sample window, 2016-01 .. 2024-09
    python scripts/factor_prescreen.py --history     # plus 1963-2015 for context

It is research, not a trial: it reads published returns and optimises nothing. It is still
looking, which is why it runs *after* the eight strategies were written down (lesson 03b §5) and
cannot change their rules. The window stops at 2024-09: the lockbox is not read here either.
"""

import argparse
import io
import math
import sys
import zipfile

import httpx

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}_CSV.zip"

# (label, file, long column, short column, the investors it stands in for)
FACTORS = [
    ("profitability (robust - weak OP)", "6_Portfolios_ME_OP_2x3", "BIG HiOP", "BIG LoOP",
     "buffett_quality, greenblatt_magic"),
    ("investment (conservative - aggressive)", "6_Portfolios_ME_INV_2x3", "BIG LoINV", "BIG HiINV",
     "buffett_quality"),
    ("value (high - low book/market)", "6_Portfolios_2x3", "BIG HiBM", "BIG LoBM",
     "greenblatt_magic, lynch_peg, templeton_value"),
    ("momentum (12-2 winners - losers)", "6_Portfolios_ME_Prior_12_2", "BIG HiPRIOR", "BIG LoPRIOR",
     "canslim"),
    ("long-term reversal (60-13 losers - winners)", "6_Portfolios_ME_Prior_60_13", "BIG LoPRIOR",
     "BIG HiPRIOR", "templeton_value"),
]

START, END = 201601, 202409


def monthly_block(text: str) -> dict[int, dict[str, float]]:
    """The first table in a French CSV: value-weighted monthly returns, in percent."""
    lines = text.splitlines()
    header_at = next(i for i, line in enumerate(lines)
                     if line.startswith(",") and any(c.isalpha() for c in line))
    columns = [c.strip() for c in lines[header_at].split(",")[1:]]
    out: dict[int, dict[str, float]] = {}
    for line in lines[header_at + 1:]:
        parts = [p.strip() for p in line.split(",")]
        if not parts[0].isdigit() or len(parts[0]) != 6:
            break
        out[int(parts[0])] = {c: float(v) / 100 for c, v in zip(columns, parts[1:])}
    return out


def fetch(name: str, http: httpx.Client) -> dict[int, dict[str, float]]:
    resp = http.get(BASE.format(name))
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        return monthly_block(z.read(z.namelist()[0]).decode("latin-1"))


def stats(series: list[float]) -> tuple[float, float, float]:
    """Annualised mean, annualised Sharpe, t-stat of the monthly mean."""
    n = len(series)
    mean = sum(series) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in series) / (n - 1))
    return mean * 12, (mean / sd) * math.sqrt(12) if sd else float("nan"), \
        mean / (sd / math.sqrt(n)) if sd else float("nan")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--history", action="store_true", help="also show 1963-2015")
    args = parser.parse_args()

    with httpx.Client(timeout=60, follow_redirects=True) as http:
        ff = fetch("F-F_Research_Data_Factors", http)
        windows = [("2016-01..2024-09", START, END)]
        if args.history:
            windows.insert(0, ("1963-07..2015-12", 196307, 201512))
        print(f"{'factor (BIG stocks only)':<45} {'window':<17} {'L-S /yr':>8} {'t':>6} "
              f"{'long-mkt/yr':>12} {'t':>6}   stands in for")
        for label, name, long_col, short_col, who in FACTORS:
            data = fetch(name, http)
            for window, a, b in windows:
                months = [m for m in sorted(data) if a <= m <= b and m in ff]
                spread = [data[m][long_col] - data[m][short_col] for m in months]
                market = [ff[m]["Mkt-RF"] + ff[m]["RF"] for m in months]
                excess = [data[m][long_col] - mk for m, mk in zip(months, market)]
                ls, _, t_ls = stats(spread)
                lx, _, t_lx = stats(excess)
                print(f"{label:<45} {window:<17} {ls:>8.1%} {t_ls:>6.2f} {lx:>12.1%} {t_lx:>6.2f}"
                      f"   {who}")
    print("\nL-S: long-short spread within big stocks. long-mkt: the long side alone minus the "
          "market (what a long-only strategy can actually harvest). |t| < 2 is noise.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
