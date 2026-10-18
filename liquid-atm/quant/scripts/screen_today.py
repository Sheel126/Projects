"""What the funnel would place at tomorrow's open, from the latest stored close (lesson 03 §8).

    python scripts/screen_today.py                     # flat $100k book
    python scripts/screen_today.py --equity 25000
    python scripts/screen_today.py --json

This is the same `MomentumFunnel.decide()` the backtester calls, run once on the newest session.
It reads but never writes: Phase 6 makes the Java orchestrator pull intents and own the book.
Until then the book here is flat, so held names, the heat cap and the sector cap are not applied.

It runs on lockbox dates by design. Producing today's list measures nothing; the lockbox only
forbids *scoring* the strategy on that period.

Run `data.cli daily` first, or this screens a stale close.
"""

import argparse
import json
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import psycopg  # noqa: E402

from liquid_atm_quant.backtest.panel import Panel  # noqa: E402
from liquid_atm_quant.backtest.strategy import PortfolioSnapshot  # noqa: E402
from liquid_atm_quant.config import get_settings  # noqa: E402
from liquid_atm_quant.strategy import FunnelParams, MomentumFunnel  # noqa: E402
from liquid_atm_quant.strategy.sectors import load_sectors  # noqa: E402

LOOKBACK_DAYS = 600          # calendar days: comfortably more than 252 sessions of history


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--equity", default="100000.00")
    parser.add_argument("--index", default="russell1000")
    parser.add_argument("--param", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    params = FunnelParams().with_overrides(dict(kv.split("=", 1) for kv in args.param))
    try:
        conn = psycopg.connect(get_settings().database_url, connect_timeout=5)
    except psycopg.Error as exc:
        print(f"database not reachable ({exc})", file=sys.stderr)
        return 2

    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT max(trade_date) FROM bar_segments WHERE symbol = %s",
                        (params.regime_symbol,))
            latest = cur.fetchone()[0]
        if latest is None:
            print("no bars stored; run `data.cli bars` first", file=sys.stderr)
            return 2
        panel = Panel.from_db(conn, latest - timedelta(days=LOOKBACK_DAYS), latest,
                              index_name=args.index)
        funnel = MomentumFunnel(params, sectors=load_sectors(conn))

    t = panel.session_index[latest]
    equity = Decimal(args.equity)
    book = PortfolioSnapshot(latest, equity, equity, equity, {}, frozenset())
    decision = funnel.decide(panel.view(t), book)

    if args.json:
        print(json.dumps({
            "as_of": str(latest), "regime": decision.regime.state.value,
            "regime_detail": decision.regime.describe(), "funnel": decision.screen.counts,
            "candidates": [{"symbol": c.symbol, "sector": c.sector, "momentum": c.momentum,
                            "rvol": c.rvol, "close": str(c.close), "atr": str(c.atr)}
                           for c in decision.screen.candidates],
            "intents": [{"symbol": i.symbol, "entry_limit": str(i.entry_limit),
                         "stop_loss": str(i.stop_loss), "take_profit": str(i.take_profit),
                         "notional": str(i.notional), "time_stop_days": i.time_stop_days,
                         "reason": i.reason} for i in decision.intents],
        }, indent=2))
        return 0

    print(f"as of the close of {latest}  (params {params.fingerprint()})")
    print(f"regime  {decision.regime.describe()}")
    print("funnel  " + " -> ".join(f"{k} {v}" for k, v in decision.screen.counts.items()))
    if not decision.screen.candidates:
        print("\nno candidates today")
        return 0
    print(f"\n{'symbol':<7} {'sector':<24} {'mom':>5} {'rvol':>5} {'close':>9} {'atr':>7}")
    for c in decision.screen.candidates:
        print(f"{c.symbol:<7} {c.sector:<24} {c.momentum:>5.2f} {c.rvol:>5.1f} {c.close:>9} "
              f"{c.atr:>7}")
    print(f"\nintents for the next session ({len(decision.intents)})")
    for i in decision.intents:
        print(f"  BUY {i.symbol:<6} limit {i.entry_limit:>9}  stop {i.stop_loss:>9}  "
              f"target {i.take_profit:>9}  notional {i.notional:>10}  time stop "
              f"{i.time_stop_days}d")
    skipped = {k: v for k, v in decision.book.skipped.items() if v}
    if skipped:
        print(f"  skipped by the book: {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
