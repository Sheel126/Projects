"""The price panel and the point-in-time cursor (lesson 02 §1, §11).

`Panel` loads the whole backtest window once into dense `[session, symbol]` arrays. `DataView` is a
cursor pinned at one session that refuses to hand out anything later. That refusal is the
structural look-ahead defence: a strategy cannot read tomorrow's bar even by accident, because the
array it is given is sliced at `t`.

Prices in here are **raw** (as traded) plus `adj_factor`, exactly as Phase 1 stored them. The rule
from lesson 01 §2 applies unchanged: orders and price-level filters use raw, returns and indicators
use adjusted (`raw * adj_factor`).
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
import psycopg

# Bars come from `bar_segments`, which is `tradable_bars` (volume > 0) split into identity segments
# at gaps of more than 20 sessions. Never `daily_bars`: that includes frozen post-delisting padding
# (lesson 01 §5).
_BARS_SQL = """
    SELECT trade_date, symbol, open, high, low, close, volume, adj_factor, segment_id
    FROM bar_segments
    WHERE trade_date BETWEEN %(start)s AND %(end)s
      AND (%(symbols)s::text[] IS NULL OR symbol = ANY(%(symbols)s))
    ORDER BY trade_date, symbol"""

_SESSIONS_SQL = """
    SELECT trade_date FROM trading_calendar
    WHERE trade_date BETWEEN %(start)s AND %(end)s ORDER BY trade_date"""

# Point-in-time membership: the latest snapshot that existed at or before each session
# (lesson 01 §3). Never the nearest snapshot, which would be look-ahead.
_MEMBERSHIP_SQL = """
    WITH sessions AS (
        SELECT trade_date FROM trading_calendar
        WHERE trade_date BETWEEN %(start)s AND %(end)s),
    effective AS (
        SELECT s.trade_date,
               (SELECT max(x.as_of_date) FROM universe_snapshots x
                WHERE x.index_name = %(index_name)s AND x.as_of_date <= s.trade_date) AS as_of_date
        FROM sessions s)
    SELECT e.trade_date, m.symbol
    FROM effective e
    JOIN universe_membership m
      ON m.index_name = %(index_name)s AND m.as_of_date = e.as_of_date"""

FIELDS = ("open", "high", "low", "close", "volume", "adj_factor")


class Panel:
    """Dense price arrays plus a point-in-time membership mask."""

    def __init__(self, sessions: list[date], symbols: list[str], arrays: dict[str, np.ndarray],
                 segment_id: np.ndarray, member: np.ndarray | None = None) -> None:
        self.sessions = list(sessions)
        self.symbols = list(symbols)
        self.index = {symbol: i for i, symbol in enumerate(self.symbols)}
        self.session_index = {day: i for i, day in enumerate(self.sessions)}
        self.arrays = arrays
        self.segment_id = segment_id
        self.member = member if member is not None else np.ones(segment_id.shape, dtype=bool)
        # Read-only from here on: the panel is shared by every DataView, and a strategy that
        # scribbled on a slice of it would silently corrupt every later session.
        for array in (*arrays.values(), segment_id):
            array.flags.writeable = False
        self._adjusted: dict[str, np.ndarray] = {}

    @property
    def shape(self) -> tuple[int, int]:
        return self.segment_id.shape

    def column(self, field: str) -> np.ndarray:
        return self.arrays[field]

    def adjusted(self, field: str = "close") -> np.ndarray:
        """Split/dividend-adjusted series: safe for returns and indicators, not for price levels.

        Cached, because a screener asks for this once per symbol per rebalance and the product is
        the whole `[session, symbol]` array. Recomputing it each time dominated the runtime of a
        full backtest, which Phase 4 has to run hundreds of times (lesson 02 §11).
        """
        cached = self._adjusted.get(field)
        if cached is None:
            cached = self.arrays[field] * self.arrays["adj_factor"]
            cached.flags.writeable = False
            self._adjusted[field] = cached
        return cached

    # ---- loading ---------------------------------------------------------------------

    @classmethod
    def from_db(cls, conn: psycopg.Connection, start: date, end: date,
                symbols: list[str] | None = None, index_name: str | None = None) -> "Panel":
        params = {"start": start, "end": end, "symbols": symbols}
        with conn.cursor() as cur:
            cur.execute(_SESSIONS_SQL, params)
            sessions = [row[0] for row in cur.fetchall()]
            cur.execute(_BARS_SQL, params)
            rows = cur.fetchall()
        if not sessions:
            raise ValueError(f"trading_calendar has no sessions in {start}..{end}; "
                             "run `data.cli sync-calendar` first")
        if not rows:
            raise ValueError(f"bar_segments is empty for {start}..{end}; run `data.cli bars` first")

        frame = pd.DataFrame(rows, columns=["trade_date", "symbol", "open", "high", "low", "close",
                                            "volume", "adj_factor", "segment_id"])
        panel = cls._from_frame(frame, sessions)
        if index_name:
            panel.member = panel._load_membership(conn, index_name, start, end)
        return panel

    @classmethod
    def from_frame(cls, frame: pd.DataFrame, sessions: list[date] | None = None) -> "Panel":
        """Build from a long frame (trade_date, symbol, o/h/l/c, volume, adj_factor, segment_id).

        Tests use this; it is the same code path the database loader ends in.
        """
        frame = frame.copy()
        if "adj_factor" not in frame:
            frame["adj_factor"] = 1.0
        if "segment_id" not in frame:
            frame["segment_id"] = 0
        if sessions is None:
            sessions = sorted(frame["trade_date"].unique())
        return cls._from_frame(frame, list(sessions))

    @classmethod
    def _from_frame(cls, frame: pd.DataFrame, sessions: list[date]) -> "Panel":
        symbols = sorted(frame["symbol"].unique())
        session_index = {day: i for i, day in enumerate(sessions)}
        symbol_index = {symbol: i for i, symbol in enumerate(symbols)}
        shape = (len(sessions), len(symbols))

        rows = frame["trade_date"].map(session_index)
        keep = rows.notna()                       # bars on non-session dates are dropped
        rows = rows[keep].to_numpy(dtype=np.int64)
        cols = frame.loc[keep, "symbol"].map(symbol_index).to_numpy(dtype=np.int64)

        arrays = {}
        for field in FIELDS:
            values = np.full(shape, np.nan, dtype=np.float64)
            values[rows, cols] = frame.loc[keep, field].to_numpy(dtype=np.float64)
            arrays[field] = values
        segment_id = np.full(shape, -1, dtype=np.int32)
        segment_id[rows, cols] = frame.loc[keep, "segment_id"].to_numpy(dtype=np.int32)
        return cls(sessions, symbols, arrays, segment_id)

    def _load_membership(self, conn: psycopg.Connection, index_name: str, start: date,
                         end: date) -> np.ndarray:
        with conn.cursor() as cur:
            cur.execute(_MEMBERSHIP_SQL,
                        {"index_name": index_name, "start": start, "end": end})
            rows = cur.fetchall()
        member = np.zeros(self.shape, dtype=bool)
        for trade_date, symbol in rows:
            i, j = self.session_index.get(trade_date), self.index.get(symbol)
            if i is not None and j is not None:
                member[i, j] = True
        return member

    def dividends(self, split_threshold: float = 0.02) -> dict[str, dict[int, float]]:
        """Per-share distributions implied by the `adj_factor` path: `{symbol: {session: amount}}`.

        Phase 1 stores raw prices plus `adj_factor = adjusted_close / raw_close`. Back-adjustment
        discounts history by every *later* distribution, so walking forward in time the factor steps
        UP on each ex-date by roughly `dividend / price`. A split moves it by 100% or more, so steps
        at or above `split_threshold` are splits and are skipped.

        This is a reconstruction, not a dividend feed - we have no free point-in-time one. It errs
        toward missing distributions, which understates the benchmark's income and its tax drag, so
        it makes buy-and-hold harder to beat rather than easier.
        """
        factor, close = self.arrays["adj_factor"], self.arrays["close"]
        out: dict[str, dict[int, float]] = {}
        for j, symbol in enumerate(self.symbols):
            f, c = factor[:, j], close[:, j]
            valid = np.flatnonzero(np.isfinite(f) & np.isfinite(c) & (f > 0))
            if valid.size < 2:
                continue
            fv, cv = f[valid], c[valid]
            step = fv[1:] / fv[:-1] - 1.0
            hits = np.flatnonzero((step > 1e-9) & (step < split_threshold))
            if hits.size:
                out[symbol] = {int(valid[k + 1]): float(cv[k + 1] * step[k]) for k in hits}
        return out

    def head(self, n: int) -> "Panel":
        """The panel as it would have been loaded with only its first `n` sessions.

        The truncation-invariance test (lesson 03 §7) compares indicators computed on this against
        the full panel: any value that changes is reading the future.
        """
        return Panel(self.sessions[:n], self.symbols,
                     {k: v[:n].copy() for k, v in self.arrays.items()},
                     self.segment_id[:n].copy(), self.member[:n].copy())

    def view(self, session: int) -> "DataView":
        return DataView(self, session)


class FutureDataError(AssertionError):
    """A strategy asked for data at or after a session it cannot know about yet."""


class DataView:
    """Read-only access to the panel up to and including session `t`.

    Every accessor slices `[:t + 1]`, so there is no way to reach a later row. This is cheaper and
    far more reliable than auditing each indicator for a missing `shift(1)`.
    """

    __slots__ = ("panel", "t")

    def __init__(self, panel: Panel, t: int) -> None:
        if not 0 <= t < len(panel.sessions):
            raise IndexError(f"session {t} outside 0..{len(panel.sessions) - 1}")
        self.panel = panel
        self.t = t

    @property
    def today(self) -> date:
        return self.panel.sessions[self.t]

    @property
    def symbols(self) -> list[str]:
        return self.panel.symbols

    def at(self, when: date) -> int:
        i = self.panel.session_index.get(when)
        if i is None:
            raise KeyError(f"{when} is not a trading session")
        if i > self.t:
            raise FutureDataError(f"{when} is after {self.today}")
        return i

    def history(self, field: str, symbol: str | None = None, lookback: int | None = None,
                adjusted: bool = False) -> np.ndarray:
        """Values up to and including today. 1-D for one symbol, 2-D for the whole panel."""
        source = self.panel.adjusted(field) if adjusted else self.panel.column(field)
        start = 0 if lookback is None else max(0, self.t + 1 - lookback)
        window = source[start:self.t + 1]
        return window if symbol is None else window[:, self.panel.index[symbol]]

    def latest(self, field: str, symbol: str | None = None, adjusted: bool = False):
        """Today's value. NaN when the symbol did not trade today."""
        row = (self.panel.adjusted(field) if adjusted else self.panel.column(field))[self.t]
        return row if symbol is None else row[self.panel.index[symbol]]

    def traded_today(self, symbol: str) -> bool:
        return not np.isnan(self.panel.column("close")[self.t, self.panel.index[symbol]])

    def segment(self, symbol: str) -> int:
        return int(self.panel.segment_id[self.t, self.panel.index[symbol]])

    def same_segment(self, symbol: str, lookback: int) -> bool:
        """True when the whole lookback belongs to one corporate identity (lesson 01 §5b).

        An indicator window that straddles two segments is measuring a ticker change, not the
        market, so the caller must skip the symbol.
        """
        segments = self.history("close", symbol, lookback)     # for length only
        ids = self.panel.segment_id[max(0, self.t + 1 - lookback):self.t + 1,
                                    self.panel.index[symbol]]
        live = ids[ids >= 0]
        return len(live) == len(segments) and bool(np.all(live == live[0]))

    def adv(self, symbol: str, window: int = 20) -> float:
        """Trailing average *dollar* volume, known at today's close.

        Position sizing is capped against this rather than against tomorrow's volume, which would
        be look-ahead in the optimistic direction (lesson 02 §3).
        """
        j = self.panel.index[symbol]
        start = max(0, self.t + 1 - window)
        volume = self.panel.column("volume")[start:self.t + 1, j]
        close = self.panel.column("close")[start:self.t + 1, j]
        dollars = volume * close
        finite = dollars[np.isfinite(dollars)]
        return float(finite.mean()) if finite.size else 0.0

    def universe(self) -> list[str]:
        """Index members as of today, restricted to names that actually traded today."""
        member = self.panel.member[self.t]
        closes = self.panel.column("close")[self.t]
        return [s for j, s in enumerate(self.panel.symbols)
                if member[j] and not np.isnan(closes[j])]

    def frame(self, symbol: str, lookback: int, adjusted: bool = False) -> pd.DataFrame:
        """A pandas window for strategies that would rather not touch numpy."""
        start = max(0, self.t + 1 - lookback)
        data = {field: self.history(field, symbol, lookback, adjusted=adjusted) for field in FIELDS}
        return pd.DataFrame(data, index=pd.Index(self.panel.sessions[start:self.t + 1],
                                                 name="trade_date"))
