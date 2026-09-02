"""Clean session reset — cancel orders, flatten, reset day baseline."""
from __future__ import annotations

import logging
import time

from finance_vibe.bot.alpaca_client import AlpacaClient
from finance_vibe.bot.market_hours import now_et
from finance_vibe.bot.store import BotStore

logger = logging.getLogger(__name__)


def prepare_clean_session(
    alpaca: AlpacaClient | None = None,
    store: BotStore | None = None,
    flatten: bool = True,
) -> dict:
    """Option A: flat book, no open orders, Day P&L baseline reset to now."""
    alpaca = alpaca or AlpacaClient()
    store = store or BotStore()
    today = now_et().date()

    if not alpaca.configured:
        raise RuntimeError("Alpaca not configured")

    report: dict = {
        "status": "completed",
        "date": today.isoformat(),
        "orders_cancelled": 0,
        "positions_closed": [],
        "equity_before": 0.0,
        "equity_after": 0.0,
    }

    acct = alpaca.get_account()
    report["equity_before"] = acct["equity"]

    try:
        open_before = alpaca.get_open_orders()
        alpaca.cancel_all_orders()
        report["orders_cancelled"] = len(open_before)
        logger.info("Cancelled %s open orders", len(open_before))
    except Exception as exc:
        logger.warning("Cancel orders: %s", exc)

    if flatten:
        try:
            closed = alpaca.close_all_positions()
            for item in closed:
                report["positions_closed"].append({
                    "symbol": item["symbol"],
                    "qty": item["qty"],
                    "status": item["order"].get("status"),
                })
                logger.info("Flatten closed %s qty=%s", item["symbol"], item["qty"])
            if closed:
                time.sleep(2.0)
        except Exception as exc:
            logger.error("Flatten all failed: %s", exc)
            positions = alpaca.get_positions()
            for pos in positions:
                sym = pos["symbol"]
                qty = float(pos["qty"])
                try:
                    order = alpaca.close_position(sym)
                    report["positions_closed"].append({
                        "symbol": sym, "qty": qty, "status": order.get("status"),
                    })
                except Exception as exc2:
                    logger.error("Flatten failed %s: %s", sym, exc2)
                    report["positions_closed"].append({
                        "symbol": sym, "qty": qty, "status": f"error:{exc2}",
                    })
            if positions:
                time.sleep(2.0)

    acct = alpaca.get_account()
    equity = acct["equity"]
    report["equity_after"] = equity

    store.set_day_start_equity(today, equity)
    store.set_state(f"entries_blocked_{today.isoformat()}", "0")
    store.set_halted_today(today, False)
    store.clear_all_pending_sells()
    store.log_activity(
        f"Clean session prepared | equity=${equity:,.2f} | "
        f"cancelled {report['orders_cancelled']} orders | "
        f"closed {len(report['positions_closed'])} positions",
        phase="prepare",
    )

    return report
