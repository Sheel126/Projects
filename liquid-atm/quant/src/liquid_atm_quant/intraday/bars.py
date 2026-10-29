"""Minute bars for the Phase 3d intraday strategies (lesson 03d §2).

Alpaca's free plan serves SIP minute bars back to 2016, which is the whole in-sample window. They
are cached under `data/cache/intraday/` as one gzipped CSV per symbol-year (about 1.5 MB for a
year of SPY), because the daily store in Postgres was never meant to hold 100k rows per symbol per
year, and a cache file is something a test can build by hand.

Only the regular session is kept: bars starting 09:30 through 15:59 New York time. Pre-market
prints would leak into the opening price and VWAP, and the strategies here never trade outside the
session.
"""

import gzip
import logging
from collections.abc import Iterable
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

log = logging.getLogger("intraday.bars")

NY = ZoneInfo("America/New_York")
CACHE = Path(__file__).resolve().parents[4] / "data" / "cache" / "intraday"
SESSION_OPEN = time(9, 30)
SESSION_LAST_BAR = time(15, 59)
COLUMNS = ["o", "h", "l", "c", "v", "vw"]


def _path(symbol: str, year: int, root: Path) -> Path:
    return root / symbol / f"{year}.csv.gz"


def rows_to_frame(rows: Iterable[dict]) -> pd.DataFrame:
    """Alpaca bar dicts -> a frame indexed by NY bar-start time, regular session only."""
    frame = pd.DataFrame(list(rows))
    if frame.empty:
        return pd.DataFrame(columns=COLUMNS, index=pd.DatetimeIndex([], tz=NY, name="t"))
    frame["t"] = pd.to_datetime(frame["t"], utc=True).dt.tz_convert(NY)
    frame = frame.set_index("t").sort_index()
    clock = frame.index.time
    frame = frame[(clock >= SESSION_OPEN) & (clock <= SESSION_LAST_BAR)]
    if "vw" not in frame:
        frame["vw"] = (frame["h"] + frame["l"] + frame["c"]) / 3
    return frame[COLUMNS].astype(float)


def download_year(client, symbol: str, year: int, root: Path = CACHE,
                  through: date | None = None) -> Path:
    """Fetch one symbol-year of 1-minute bars into the cache, month by month."""
    path = _path(symbol, year, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    last_month = 12 if through is None or through.year > year else through.month
    for month in range(1, last_month + 1):
        start = datetime(year, month, 1, 9, 0, tzinfo=NY)
        end = datetime(year + (month == 12), month % 12 + 1, 1, 0, 0, tzinfo=NY)
        if through is not None:
            end = min(end, datetime.combine(through, time(23, 59), NY))
        rows = client.intraday_bars([symbol], start, end).get(symbol, [])
        frames.append(rows_to_frame(rows))
        log.info("%s %d-%02d: %d bars", symbol, year, month, len(frames[-1]))
    frame = pd.concat(frames).sort_index()
    frame = frame[~frame.index.duplicated()]
    with gzip.open(path, "wt", newline="") as fh:
        frame.to_csv(fh, index_label="t")
    return path


def load(symbol: str, start: date, end: date, root: Path = CACHE) -> pd.DataFrame:
    """Cached minute bars for [start, end], NY-indexed. Missing years raise: download first."""
    frames = []
    for year in range(start.year, end.year + 1):
        path = _path(symbol, year, root)
        if not path.exists():
            raise FileNotFoundError(f"{path}: run scripts/run_phase3d.py --fetch-minutes first")
        frame = pd.read_csv(path, index_col="t")
        frame.index = pd.to_datetime(frame.index, utc=True).tz_convert(NY)
        frames.append(frame)
    out = pd.concat(frames).sort_index()
    days = out.index.date
    return out[(days >= start) & (days <= end)]


def by_session(frame: pd.DataFrame) -> dict[date, pd.DataFrame]:
    """Split a minute frame into one frame per session, in date order."""
    return {day: part for day, part in frame.groupby(frame.index.date)}


__all__ = ["CACHE", "NY", "by_session", "download_year", "load", "rows_to_frame"]
