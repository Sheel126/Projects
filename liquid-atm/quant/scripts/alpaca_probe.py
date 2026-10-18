"""Phase 0 Alpaca PAPER probe: record how the broker really behaves, instead of trusting the docs.

Usage (from liquid-atm/quant):  python scripts/alpaca_probe.py
Writes liquid-atm/docs/phase0/alpaca-probe-report.md. Refuses to run against a live account.
"""

import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

from liquid_atm_quant.config import get_settings

REPORT = Path(__file__).resolve().parents[2] / "docs" / "phase0" / "alpaca-probe-report.md"
PAPER_BASE = "https://paper-api.alpaca.markets"
PROBE_SYMBOL = "SPY"


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = [
            "# Alpaca paper probe report",
            "",
            f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by `quant/scripts/alpaca_probe.py`.",
            "",
        ]

    def section(self, title: str) -> None:
        self.lines += ["", f"## {title}", ""]

    def kv(self, key: str, value: object) -> None:
        self.lines.append(f"- **{key}:** `{value}`")

    def text(self, value: str) -> None:
        self.lines.append(value)

    def write(self) -> None:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def run_step(report: Report, title: str, fn) -> None:
    """Run one probe step; a failure is recorded, not fatal, so the report is always complete."""
    report.section(title)
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - we want every failure in the report
        report.kv("ERROR", f"{type(exc).__name__}: {exc}")
        report.text("\n```\n" + traceback.format_exc(limit=3) + "```")


def main() -> int:
    settings = get_settings()
    if not settings.alpaca_paper:
        print("REFUSING: ALPACA_PAPER is not true. This probe only runs against paper accounts.")
        return 2
    if not settings.has_alpaca_keys:
        print("SKIP: ALPACA_API_KEY / ALPACA_SECRET_KEY not set in liquid-atm/.env")
        return 0

    # Imported late so the script can skip cleanly without keys.
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
    from alpaca.trading.requests import (
        GetCalendarRequest,
        GetOrderByIdRequest,
        LimitOrderRequest,
        StopLossRequest,
        TakeProfitRequest,
    )

    trading = TradingClient(settings.alpaca_api_key, settings.alpaca_secret_key, paper=True)
    data = StockHistoricalDataClient(settings.alpaca_api_key, settings.alpaca_secret_key)
    report = Report()
    state: dict[str, object] = {}

    def _account():
        acct = trading.get_account()
        for field in ("status", "account_blocked", "trading_blocked", "pattern_day_trader",
                      "daytrade_count", "multiplier", "equity", "cash", "buying_power",
                      "daytrading_buying_power", "regt_buying_power", "shorting_enabled"):
            report.kv(field, getattr(acct, field, "n/a"))
        report.text("\n> `multiplier` > 1 means a margin account. We still cap exposure at 1.0x equity in software.")

    def _clock():
        clock = trading.get_clock()
        report.kv("is_open", clock.is_open)
        report.kv("next_open", clock.next_open)
        report.kv("next_close", clock.next_close)
        days = trading.get_calendar(GetCalendarRequest(start=date.today(), end=date.today() + timedelta(days=10)))
        report.kv("next trading days", ", ".join(str(d.date) for d in days[:7]))

    def _ratelimit():
        headers = {"APCA-API-KEY-ID": settings.alpaca_api_key, "APCA-API-SECRET-KEY": settings.alpaca_secret_key}
        resp = httpx.get(f"{PAPER_BASE}/v2/account", headers=headers, timeout=10)
        for name in ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"):
            report.kv(name, resp.headers.get(name, "absent"))

    def _feeds():
        latest = data.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=PROBE_SYMBOL, feed=DataFeed.IEX))
        state["last_price"] = float(latest[PROBE_SYMBOL].price)
        report.kv(f"{PROBE_SYMBOL} latest IEX trade", state["last_price"])
        # Free plan: SIP data is only available with a 15-minute delay, so end the window 20 minutes ago.
        end = datetime.now(timezone.utc) - timedelta(minutes=20)
        for feed in (DataFeed.IEX, DataFeed.SIP):
            try:
                bars = data.get_stock_bars(StockBarsRequest(
                    symbol_or_symbols=PROBE_SYMBOL, timeframe=TimeFrame.Day,
                    start=end - timedelta(days=10), end=end, feed=feed))
                rows = bars.data.get(PROBE_SYMBOL, [])
                last = rows[-1] if rows else None
                report.kv(f"daily bars feed={feed.value}",
                          f"{len(rows)} bars; last {last.timestamp.date()} close={last.close} vol={last.volume}"
                          if last else "0 bars")
            except Exception as exc:  # noqa: BLE001
                report.kv(f"daily bars feed={feed.value}", f"ERROR {type(exc).__name__}: {exc}")
        report.text("\n> SIP volume is the consolidated tape; IEX is a single venue (~2-3% of volume). "
                    "Volume-breakout signals must use SIP daily bars.")

    def _bracket():
        last = state.get("last_price")
        if not isinstance(last, float):
            report.kv("skipped", "no reference price from step 4")
            return
        entry = round(last * 0.5, 2)           # 50% below market: will never fill
        take_profit = round(entry * 1.10, 2)
        stop_loss = round(entry * 0.95, 2)
        order = trading.submit_order(LimitOrderRequest(
            symbol=PROBE_SYMBOL, qty=1, side=OrderSide.BUY, time_in_force=TimeInForce.DAY,
            limit_price=entry, order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=take_profit),
            stop_loss=StopLossRequest(stop_price=stop_loss),
            client_order_id=f"probe-{datetime.now(timezone.utc):%Y%m%d%H%M%S}",
        ))
        try:
            report.kv("accepted", True)
            report.kv("entry / TP / SL", f"{entry} / {take_profit} / {stop_loss}")
            full = trading.get_order_by_id(order.id, GetOrderByIdRequest(nested=True))
            report.kv("parent", f"type={full.type} class={full.order_class} status={full.status} tif={full.time_in_force}")
            for leg in full.legs or []:
                report.kv("child leg", f"type={leg.type} side={leg.side} status={leg.status} "
                                       f"limit={leg.limit_price} stop={leg.stop_price}")
        finally:
            trading.cancel_order_by_id(order.id)
            after = trading.get_order_by_id(order.id)
            report.kv("after cancel", f"status={after.status}")

    for title, fn in (
        ("1. Account flags (PDT, margin, buying power)", _account),
        ("2. Market clock and calendar", _clock),
        ("3. Rate-limit headers", _ratelimit),
        ("4. Market data feeds (free tier)", _feeds),
        ("5. Limit-entry bracket order (submitted far from market, then cancelled)", _bracket),
    ):
        run_step(report, title, fn)

    report.section("Notes")
    report.text("- OCO (exit-only) orders need an existing position, so they are probed in Phase 6 on paper fills.")
    report.text("- Brackets do not support extended hours; entries are regular-session only.")
    report.write()
    print(f"Report written to {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
