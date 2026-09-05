"""Compare the bot's daily results against buying QQQ at the open and selling at the close.

This is the only honest scoreboard for a long-only intraday strategy: if it
cannot beat holding the index for the same hours, the machinery is not earning
its keep. Prints per-day bot vs benchmark, and the two numbers that decide the
two-week run: green-day percentage and total return versus QQQ.

Usage:
  python scripts/benchmark.py
  python scripts/benchmark.py --symbol SPY --start 2026-08-31
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_lp = Path(__file__).resolve().parent.parent / "src" / "finance_vibe" / "bot" / "_load_path.py"
_spec = importlib.util.spec_from_file_location("fv_load_path", _lp)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

import argparse
import sqlite3
from datetime import date, datetime, time as dtime
from zoneinfo import ZoneInfo

from finance_vibe.bot import config

ET = ZoneInfo("America/New_York")


def bot_days(start: date | None, end: date | None) -> list[tuple[date, float]]:
    """Realised day P&L percent per session.

    The last equity snapshot of each day carries that day's P&L; the EOD
    report is authoritative where it exists, so it wins.
    """
    conn = sqlite3.connect(str(config.BOT_DB_PATH))
    pnl: dict[date, float] = {}

    for created, day_pnl in conn.execute(
        "SELECT created_at, day_pnl_pct FROM equity_snapshots "
        "WHERE day_pnl_pct IS NOT NULL ORDER BY created_at"
    ):
        try:
            d = datetime.fromisoformat(created).astimezone(ET).date()
        except ValueError:
            continue
        pnl[d] = float(day_pnl)

    for trade_date, pct in conn.execute(
        "SELECT trade_date, pnl_pct FROM daily_reports WHERE pnl_pct IS NOT NULL"
    ):
        try:
            pnl[date.fromisoformat(str(trade_date))] = float(pct)
        except ValueError:
            continue
    conn.close()

    return [
        (d, v) for d, v in sorted(pnl.items())
        if d.weekday() < 5
        and not (start and d < start)
        and not (end and d > end)
    ]


def benchmark_days(symbol: str, days: list[date]) -> dict[date, float]:
    """Open-to-close percent for the benchmark on each session."""
    if not days:
        return {}
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    from finance_vibe.bot.alpaca_client import AlpacaClient

    client = AlpacaClient()
    if not client.configured:
        print("  (Alpaca not configured — benchmark unavailable)")
        return {}
    client._ensure_clients()
    try:
        res = client._data.get_stock_bars(StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame(amount=1, unit=TimeFrameUnit.Minute),
            start=datetime.combine(min(days), dtime(9, 0), tzinfo=ET),
            end=datetime.combine(max(days), dtime(20, 0), tzinfo=ET),
            feed="iex",
        ))
    except Exception as exc:
        print(f"  (benchmark fetch failed: {exc})")
        return {}

    opens: dict[date, float] = {}
    closes: dict[date, float] = {}
    for bar in res.data.get(symbol, []):
        t = bar.timestamp.astimezone(ET)
        if not (dtime(9, 30) <= t.time() <= dtime(16, 0)):
            continue
        if t.date() not in opens:
            opens[t.date()] = float(bar.open)
        closes[t.date()] = float(bar.close)

    return {
        d: (closes[d] / opens[d] - 1) * 100
        for d in opens if d in closes
    }


def basket_days(days: list[date]) -> dict[date, float]:
    """Equal-weight open-to-close of the watchlist itself.

    This is the comparison that actually matters. The watchlist runs about
    2.5x QQQ's volatility, so beating QQQ proves nothing — a monkey holding
    these 14 names would beat QQQ in any rising market. The bot only has an
    edge if it beats this basket scaled to the same capital it deploys.
    """
    per_symbol = {s: benchmark_days(s, days) for s in config.WATCHLIST}
    out: dict[date, float] = {}
    for d in days:
        vals = [m[d] for m in per_symbol.values() if d in m]
        if vals:
            out[d] = sum(vals) / len(vals)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Bot vs buy-and-hold-the-index")
    p.add_argument("--symbol", default="QQQ")
    p.add_argument("--start", type=date.fromisoformat)
    p.add_argument("--end", type=date.fromisoformat)
    p.add_argument("--exposure", type=float, default=0.48,
                   help="average fraction of capital the bot deploys, for the "
                        "beta-matched comparison (see replay.py output)")
    p.add_argument("--alpha", action="store_true",
                   help="also compare against the watchlist basket (the honest test)")
    args = p.parse_args(argv)

    days = bot_days(args.start, args.end)
    if not days:
        raise SystemExit("no stored sessions with a day baseline")
    bench = benchmark_days(args.symbol, [d for d, _ in days])

    print(f"\n{'day':<12}{'bot':>9}{args.symbol:>9}{'edge':>9}")
    print("-" * 39)
    bot_total = bench_total = 0.0
    green = wins = compared = 0
    for d, pct in days:
        bot_total += pct
        green += pct > 0
        b = bench.get(d)
        if b is None:
            print(f"{d!s:<12}{pct:>+8.2f}%{'—':>9}{'—':>9}")
            continue
        bench_total += b
        compared += 1
        wins += pct > b
        print(f"{d!s:<12}{pct:>+8.2f}%{b:>+8.2f}%{pct - b:>+8.2f}%")

    n = len(days)
    print("-" * 39)
    print(f"{'total':<12}{bot_total:>+8.2f}%{bench_total:>+8.2f}%"
          f"{bot_total - bench_total:>+8.2f}%")
    print(f"\n  green days     {green}/{n}  ({green / n * 100:.0f}%)")
    if compared:
        print(f"  beat {args.symbol}       {wins}/{compared}  ({wins / compared * 100:.0f}%)")

    if args.alpha:
        basket = basket_days([d for d, _ in days])
        b_total = sum(basket.get(d, 0.0) for d, _ in days)
        matched = b_total * args.exposure
        print(f"\n  {'-' * 56}")
        print("  THE HONEST TEST — is there any skill, or just market exposure?")
        print(f"  {'-' * 56}")
        print(f"  watchlist basket, equal weight, open->close   {b_total:>+7.2f}%")
        print(f"  same basket at the bot's {args.exposure * 100:.0f}% exposure         "
              f"{matched:>+7.2f}%")
        print(f"  the bot                                       {bot_total:>+7.2f}%")
        print(f"  ALPHA (skill above holding the basket)        {bot_total - matched:>+7.2f}%")
        print("\n  Alpha near zero means the returns are market exposure, not")
        print("  selection or timing. Judge the run on this line, not green days:")
        print("  in a rising market green days are almost free.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
