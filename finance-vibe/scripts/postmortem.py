"""Day post-mortem: what we did, what we skipped, and what each cost.

Run after the close:

    PYTHONPATH=src python scripts/postmortem.py              # today
    PYTHONPATH=src python scripts/postmortem.py --date 2026-09-03
    PYTHONPATH=src python scripts/postmortem.py --days 5

It answers the question the bot could not answer before: on a day we should
have made money, where exactly did it go wrong? It does that by replaying
the rest of the session against every decision:

  * for each trade, how far it ran in our favour before we exited (MFE), how
    far against us (MAE), and what we left on the table after selling
  * for each REJECTED candidate, what the stock went on to do — so a gate
    that keeps blocking winners shows up as a dollar cost, not an opinion

Read-only with respect to trading. It only backfills outcome columns.
"""
from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

from finance_vibe.bot import config
from finance_vibe.bot.alpaca_client import AlpacaClient

ET = ZoneInfo("America/New_York")


def minute_bars(client: AlpacaClient, symbols: list[str], day: date) -> dict:
    """Minute bars for one past session, keyed by symbol."""
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    client._ensure_clients()
    out: dict[str, list] = {}
    # Chunked so a long watchlist cannot blow the URL/response limits.
    for i in range(0, len(symbols), 10):
        chunk = symbols[i : i + 10]
        try:
            res = client._data.get_stock_bars(
                StockBarsRequest(
                    symbol_or_symbols=chunk,
                    timeframe=TimeFrame(amount=1, unit=TimeFrameUnit.Minute),
                    start=datetime.combine(day, dtime(9, 30), tzinfo=ET),
                    end=datetime.combine(day, dtime(16, 0), tzinfo=ET),
                    feed="iex",
                )
            )
            for sym in chunk:
                out[sym] = list(res.data.get(sym, []))
        except Exception as exc:  # noqa: BLE001
            print(f"  ! bars failed for {chunk}: {exc}")
    return out


def _window(bars: list, start: datetime, end: datetime | None = None) -> list:
    return [
        b for b in bars
        if b.timestamp >= start and (end is None or b.timestamp <= end)
    ]


def enrich(conn: sqlite3.Connection, client: AlpacaClient, day: date) -> None:
    """Backfill 'what happened next' for every decision made that day."""
    ds = day.isoformat()
    syms = {
        r[0] for r in conn.execute(
            "SELECT DISTINCT ticker FROM eligibility WHERE trade_date = ? "
            "UNION SELECT DISTINCT ticker FROM trades WHERE trade_date = ?",
            (ds, ds),
        )
    }
    if not syms:
        return
    bars = minute_bars(client, sorted(syms), day)

    # Rejected and accepted candidates: how did the stock do from here?
    for row in conn.execute(
        "SELECT id, ticker, created_at, price FROM eligibility "
        "WHERE trade_date = ? AND close_price IS NULL", (ds,),
    ).fetchall():
        b = bars.get(row["ticker"]) or []
        if not b or not row["price"]:
            continue
        try:
            seen = datetime.fromisoformat(row["created_at"])
        except ValueError:
            continue
        rest = _window(b, seen)
        if not rest:
            continue
        px = float(row["price"])
        hi = max(x.high for x in rest)
        lo = min(x.low for x in rest)
        close = rest[-1].close
        conn.execute(
            """UPDATE eligibility SET close_price = ?, max_gain_after_pct = ?,
               max_drop_after_pct = ?, to_close_pct = ? WHERE id = ?""",
            (
                close, (hi / px - 1) * 100, (lo / px - 1) * 100,
                (close / px - 1) * 100, row["id"],
            ),
        )

    # Trades: did we exit too early, too late, or enter badly?
    for row in conn.execute(
        "SELECT id, ticker, entry_at, exit_at, entry_price, exit_price "
        "FROM trades WHERE trade_date = ? AND status = 'closed' "
        "AND close_price IS NULL", (ds,),
    ).fetchall():
        b = bars.get(row["ticker"]) or []
        if not b or not row["entry_at"] or not row["entry_price"]:
            continue
        try:
            t_in = datetime.fromisoformat(row["entry_at"])
            t_out = datetime.fromisoformat(row["exit_at"]) if row["exit_at"] else None
        except ValueError:
            continue
        held = _window(b, t_in, t_out)
        after = _window(b, t_out) if t_out else []
        if not held:
            continue
        entry = float(row["entry_price"])
        mfe = (max(x.high for x in held) / entry - 1) * 100
        mae = (min(x.low for x in held) / entry - 1) * 100
        missed = None
        if after and row["exit_price"]:
            missed = (
                max(x.high for x in after) / float(row["exit_price"]) - 1
            ) * 100
        conn.execute(
            """UPDATE trades SET mfe_pct = ?, mae_pct = ?,
               missed_after_exit_pct = ?, close_price = ? WHERE id = ?""",
            (mfe, mae, missed, b[-1].close, row["id"]),
        )
    conn.commit()


def report(conn: sqlite3.Connection, day: date) -> None:
    ds = day.isoformat()
    trades = [
        dict(r) for r in conn.execute(
            "SELECT * FROM trades WHERE trade_date = ? AND status = 'closed' "
            "ORDER BY entry_at", (ds,),
        )
    ]
    elig = [
        dict(r) for r in conn.execute(
            "SELECT * FROM eligibility WHERE trade_date = ?", (ds,),
        )
    ]
    rpt = conn.execute(
        "SELECT * FROM daily_reports WHERE trade_date = ?", (ds,),
    ).fetchone()

    print(f"\n{'=' * 74}")
    print(f"  POST-MORTEM  {ds}")
    print(f"{'=' * 74}")
    if rpt:
        print(f"  day P&L {rpt['pnl_pct']:+.2f}%  "
              f"({rpt['equity_start']:,.0f} -> {rpt['equity_end']:,.0f})  "
              f"cycles={rpt['num_cycles']}")
    if not trades and not elig:
        print("  no logged activity for this date.")
        return

    if trades:
        print(f"\n  WHAT WE TRADED ({len(trades)} round trips)")
        print(f"  {'tkr':6}{'in':>8}{'out':>8}{'P&L%':>8}{'best':>8}"
              f"{'worst':>8}{'left':>8}{'min':>6}  why")
        print(f"  {'-' * 70}")
        for t in trades:
            print(
                f"  {t['ticker']:6}{t['entry_price'] or 0:>8.2f}"
                f"{t['exit_price'] or 0:>8.2f}{t['pnl_pct'] or 0:>+8.2f}"
                f"{t['mfe_pct'] or 0:>+8.2f}{t['mae_pct'] or 0:>+8.2f}"
                f"{t['missed_after_exit_pct'] or 0:>+8.2f}"
                f"{t['hold_minutes'] or 0:>6.0f}  "
                f"{(t['entry_reason'] or '')[:24]}"
            )
        tot = sum(t["pnl_pct"] or 0 for t in trades)
        wins = sum(1 for t in trades if (t["pnl_pct"] or 0) > 0)
        print(f"  {'-' * 70}")
        print(f"  sum of trade returns {tot:+.2f}%   "
              f"win rate {wins}/{len(trades)}")

        # Exit quality: the number that says "your target is wrong".
        early = [
            t for t in trades
            if (t["missed_after_exit_pct"] or 0) > 0.5 and (t["pnl_pct"] or 0) > 0
        ]
        late = [
            t for t in trades
            if (t["mfe_pct"] or 0) > 0.5 and (t["pnl_pct"] or 0) < 0
        ]
        print("\n  EXIT QUALITY")
        print(f"    sold too early (ran >0.5% more after we sold) : "
              f"{len(early)}")
        if early:
            print(f"      left behind: "
                  f"{sum(t['missed_after_exit_pct'] for t in early):+.2f}% "
                  f"({', '.join(t['ticker'] for t in early[:6])})")
        print(f"    held too long (was >0.5% up, exited red)      : "
              f"{len(late)}")
        if late:
            print(f"      gave back: "
                  f"{sum(t['mfe_pct'] - (t['pnl_pct'] or 0) for t in late):+.2f}% "
                  f"({', '.join(t['ticker'] for t in late[:6])})")

    # The headline feature: price every gate that blocked a trade.
    rejected = [e for e in elig if not e["passed"] and not e["in_position"]]
    if rejected:
        print(f"\n  WHAT EACH GATE COST US ({len(rejected)} rejections)")
        cost: dict[str, list[float]] = defaultdict(list)
        for e in rejected:
            if e["max_gain_after_pct"] is not None:
                cost[e["reject_reason"] or "unknown"].append(
                    e["max_gain_after_pct"]
                )
        if cost:
            print(f"  {'gate that blocked':<34}{'n':>5}{'avg best move after':>21}")
            print(f"  {'-' * 60}")
            for gate, vals in sorted(
                cost.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])
            ):
                avg = sum(vals) / len(vals)
                flag = "  <-- blocking winners" if avg > 0.8 else ""
                print(f"  {gate[:33]:<34}{len(vals):>5}{avg:>20.2f}%{flag}")
            print("\n  A gate with a high average is rejecting stocks that then")
            print("  went up. That is where the money is being left.")

        best = sorted(
            (e for e in rejected if e["max_gain_after_pct"] is not None),
            key=lambda e: -e["max_gain_after_pct"],
        )[:8]
        if best:
            print(f"\n  BIGGEST MISSES")
            print(f"  {'tkr':6}{'at':>7}{'px':>9}{'ran to':>9}{'score':>7}  blocked by")
            for e in best:
                t = (e["created_at"] or "")[11:16]
                print(
                    f"  {e['ticker']:6}{t:>7}{e['price'] or 0:>9.2f}"
                    f"{e['max_gain_after_pct']:>+9.2f}"
                    f"{e['quality_score'] or 0:>7.0f}  "
                    f"{(e['reject_reason'] or '')[:30]}"
                )

    passed = [e for e in elig if e["passed"]]
    if elig:
        print(f"\n  FUNNEL: {len(elig)} ticker-cycles logged, "
              f"{len(passed)} passed all gates, {len(trades)} became trades")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (default: today ET)")
    ap.add_argument("--days", type=int, default=1,
                    help="report the last N sessions")
    ap.add_argument("--no-enrich", action="store_true",
                    help="skip fetching bars; report stored data only")
    args = ap.parse_args()

    end = (
        date.fromisoformat(args.date) if args.date
        else datetime.now(ET).date()
    )
    conn = sqlite3.connect(str(config.BOT_DB_PATH))
    conn.row_factory = sqlite3.Row
    client = None if args.no_enrich else AlpacaClient()

    days: list[date] = []
    d = end
    while len(days) < args.days:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)

    for day in reversed(days):
        if client is not None:
            try:
                enrich(conn, client, day)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! enrich failed for {day}: {exc}")
        report(conn, day)
    print()


if __name__ == "__main__":
    main()
