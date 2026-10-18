from datetime import date, datetime, timezone

import httpx
import pytest
import respx

from liquid_atm_quant.data.alpaca_data import AlpacaData
from liquid_atm_quant.infra.rate_limiter import SlidingWindowRateLimiter


@pytest.fixture
def api(redis_client):
    limiter = SlidingWindowRateLimiter(redis_client, "alpaca-test", limit=100, window_ms=60_000)
    return AlpacaData("key", "secret", limiter, http=httpx.Client())


def bar(day: str, close: float) -> dict:
    return {"t": f"{day}T05:00:00Z", "o": close, "h": close + 1, "l": close - 1, "c": close, "v": 1000, "vw": close}


@respx.mock
def test_daily_bars_paginates_and_computes_adjustment_factor(api):
    def handler(request):
        params = dict(request.url.params)
        if params["adjustment"] == "raw":
            if "page_token" not in params:
                return httpx.Response(200, json={"bars": {"AAPL": [bar("2020-08-28", 499.23)]},
                                                 "next_page_token": "p2"})
            return httpx.Response(200, json={"bars": {"AAPL": [bar("2020-08-31", 129.04)]}, "next_page_token": None})
        return httpx.Response(200, json={"bars": {"AAPL": [bar("2020-08-28", 120.96), bar("2020-08-31", 125.06)]},
                                         "next_page_token": None})

    route = respx.get("https://data.alpaca.markets/v2/stocks/bars").mock(side_effect=handler)
    bars = api.daily_bars(["AAPL"], date(2020, 8, 28), date(2020, 8, 31))

    assert route.call_count == 3  # 2 raw pages + 1 adjusted page
    assert [b.trade_date for b in bars] == [date(2020, 8, 28), date(2020, 8, 31)]
    assert bars[0].close == 499.23                       # raw price is stored
    assert bars[0].adj_factor == pytest.approx(120.96 / 499.23)   # 4:1 split + dividends
    assert bars[0].close * bars[0].adj_factor == pytest.approx(120.96)
    assert bars[0].source == "alpaca_sip"
    assert route.calls[0].request.headers["APCA-API-KEY-ID"] == "key"


@respx.mock
def test_missing_adjusted_row_falls_back_to_factor_one(api):
    respx.get("https://data.alpaca.markets/v2/stocks/bars").mock(
        return_value=httpx.Response(200, json={"bars": {"XYZ": [bar("2021-01-04", 10.0)]}, "next_page_token": None}))
    # Same response for both adjustments; factor is 1 either way.
    assert api.daily_bars(["XYZ"], date(2021, 1, 4), date(2021, 1, 4))[0].adj_factor == 1.0


def test_end_bound_respects_sip_embargo():
    now = datetime(2026, 9, 18, 18, 0, tzinfo=timezone.utc)  # 14:00 ET, mid-session
    # Asking for today clips to now-16min...
    assert AlpacaData._end_bound(date(2026, 9, 18), now) == "2026-09-18T17:44:00Z"
    # ...while a past day keeps its own end-of-day bound.
    assert AlpacaData._end_bound(date(2026, 9, 17), now) == "2026-09-18T03:59:59Z"
