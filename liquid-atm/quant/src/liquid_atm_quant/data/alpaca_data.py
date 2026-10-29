"""Alpaca REST client for daily bars, assets and the trading calendar.

Plain HTTP (not alpaca-py) so every page request passes through our shared Redis rate
limiter; alpaca-py paginates internally where we cannot meter it.
"""

from collections.abc import Iterator, Sequence
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from liquid_atm_quant.data.db import Bar
from liquid_atm_quant.infra.rate_limiter import SlidingWindowRateLimiter

DATA_URL = "https://data.alpaca.markets"
PAPER_URL = "https://paper-api.alpaca.markets"
NY = ZoneInfo("America/New_York")
SYMBOLS_PER_REQUEST = 100
# Free plan: SIP data from the last 15 minutes is embargoed.
SIP_EMBARGO = timedelta(minutes=16)


class AlpacaData:
    def __init__(self, key: str, secret: str, limiter: SlidingWindowRateLimiter,
                 http: httpx.Client | None = None) -> None:
        self._headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self._limiter = limiter
        self._http = http or httpx.Client(timeout=60)

    def _get(self, url: str, params: dict) -> dict | list:
        self._limiter.acquire()
        resp = self._http.get(url, params=params, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    # ---- bars -------------------------------------------------------------------------

    @staticmethod
    def _end_bound(end: date, now: datetime | None = None) -> str:
        """End of `end`'s NY day, clipped to the SIP embargo."""
        bound = datetime.combine(end, time(23, 59, 59), NY).astimezone(timezone.utc)
        latest = (now or datetime.now(timezone.utc)) - SIP_EMBARGO
        return min(bound, latest).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _pages(self, symbols: Sequence[str], start: date, end: date, adjustment: str) -> Iterator[dict]:
        params = {
            "symbols": ",".join(symbols), "timeframe": "1Day", "feed": "sip",
            "adjustment": adjustment, "start": start.isoformat(), "end": self._end_bound(end),
            "limit": 10_000, "sort": "asc",
        }
        while True:
            body = self._get(f"{DATA_URL}/v2/stocks/bars", params)
            yield body.get("bars") or {}
            token = body.get("next_page_token")
            if not token:
                return
            params = {**params, "page_token": token}

    def _collect(self, symbols: Sequence[str], start: date, end: date, adjustment: str) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for page in self._pages(symbols, start, end, adjustment):
            for sym, rows in page.items():
                out.setdefault(sym, []).extend(rows)
        return out

    def daily_bars(self, symbols: Sequence[str], start: date, end: date) -> list[Bar]:
        """Raw OHLCV plus adj_factor = fully-adjusted close / raw close (see lesson 01 §2)."""
        bars: list[Bar] = []
        for i in range(0, len(symbols), SYMBOLS_PER_REQUEST):
            chunk = symbols[i:i + SYMBOLS_PER_REQUEST]
            raw = self._collect(chunk, start, end, "raw")
            adjusted = self._collect(chunk, start, end, "all")
            for sym, rows in raw.items():
                adj_close = {r["t"][:10]: r["c"] for r in adjusted.get(sym, [])}
                for r in rows:
                    day = r["t"][:10]
                    factor = adj_close[day] / r["c"] if day in adj_close and r["c"] else 1.0
                    bars.append(Bar(sym, date.fromisoformat(day), r["o"], r["h"], r["l"], r["c"],
                                    int(r["v"]), r.get("vw"), round(factor, 10), "alpaca_sip"))
        return bars

    def intraday_bars(self, symbols: Sequence[str], start: datetime, end: datetime,
                      timeframe: str = "1Min") -> dict[str, list[dict]]:
        """Raw (unadjusted) intraday SIP bars between two instants, keyed by symbol (Phase 3d).

        Raw on purpose: an intraday strategy trades the printed price, and a day's own bars never
        straddle a split. Rows keep Alpaca's keys: t (UTC, bar start), o, h, l, c, v, vw, n.
        """
        params = {
            "symbols": ",".join(symbols), "timeframe": timeframe, "feed": "sip",
            "adjustment": "raw", "start": start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": 10_000, "sort": "asc",
        }
        out: dict[str, list[dict]] = {}
        while True:
            body = self._get(f"{DATA_URL}/v2/stocks/bars", params)
            for sym, rows in (body.get("bars") or {}).items():
                out.setdefault(sym, []).extend(rows)
            token = body.get("next_page_token")
            if not token:
                return out
            params = {**params, "page_token": token}

    # ---- reference data ----------------------------------------------------------------

    def assets(self) -> list[dict]:
        """All US equity assets, active AND inactive (inactive = delisted: needed for history)."""
        return self._get(f"{PAPER_URL}/v2/assets", {"status": "all", "asset_class": "us_equity"})

    def calendar(self, start: date, end: date) -> list[tuple[date, datetime, datetime, bool]]:
        rows = self._get(f"{PAPER_URL}/v2/calendar", {"start": start.isoformat(), "end": end.isoformat()})
        out = []
        for r in rows:
            d = date.fromisoformat(r["date"])
            open_t = datetime.combine(d, time.fromisoformat(r["open"]), NY)
            close_t = datetime.combine(d, time.fromisoformat(r["close"]), NY)
            out.append((d, open_t, close_t, close_t.hour < 16))
        return out
