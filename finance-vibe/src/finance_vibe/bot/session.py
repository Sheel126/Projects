"""Clean session reset / resume after outage."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from finance_vibe.bot import config
from finance_vibe.bot.alpaca_client import AlpacaClient
from finance_vibe.bot.market_hours import is_market_open, now_et
from finance_vibe.bot.store import BotStore

logger = logging.getLogger(__name__)


def runner_pid_path() -> Path:
    return config.BOT_DATA_DIR / "runner.pid"


def read_alive_runner_pid() -> int | None:
    """PID of a live runner, or None if the lock is stale/missing."""
    path = runner_pid_path()
    if not path.exists():
        return None
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None
    if pid <= 0 or pid == os.getpid():
        return None
    try:
        os.kill(pid, 0)
        return pid
    except (OSError, ProcessLookupError):
        return None


def write_runner_pid() -> Path:
    config.ensure_dirs()
    path = runner_pid_path()
    path.write_text(str(os.getpid()), encoding="utf-8")
    return path


def clear_runner_pid() -> None:
    path = runner_pid_path()
    try:
        if path.exists() and path.read_text(encoding="utf-8").strip() == str(os.getpid()):
            path.unlink()
    except OSError:
        pass


def prepare_clean_session(
    alpaca: AlpacaClient | None = None,
    store: BotStore | None = None,
    flatten: bool = True,
    reset_day_baseline: bool | None = None,
) -> dict:
    """Cancel orders; optionally flatten; optionally reset Day P&L baseline.

    flatten=True (default morning start): flat book + new day baseline.
    flatten=False (resume after outage): keep positions + keep day_start_equity.
    """
    alpaca = alpaca or AlpacaClient()
    store = store or BotStore()
    today = now_et().date()
    if reset_day_baseline is None:
        reset_day_baseline = flatten

    if not alpaca.configured:
        raise RuntimeError("Alpaca not configured")

    report: dict = {
        "status": "completed",
        "mode": "flatten" if flatten else "resume",
        "date": today.isoformat(),
        "orders_cancelled": 0,
        "positions_closed": [],
        "equity_before": 0.0,
        "equity_after": 0.0,
        "day_start_equity": None,
    }

    acct = alpaca.get_account()
    report["equity_before"] = acct["equity"]

    if flatten:
        live = read_alive_runner_pid()
        if live is not None:
            msg = (
                f"Runner already running (pid {live}). "
                "Do not flatten — close that window, or use -Resume after it is stopped."
            )
            logger.error(msg)
            report["status"] = "refused"
            report["error"] = msg
            return report
        if is_market_open() and store.get_day_start_equity(today) is not None:
            msg = (
                "Market is open and today's session already started. "
                "Full start would flatten live positions and reset day PnL. "
                "Use .\\start-paper-bot.ps1 -Resume"
            )
            logger.error(msg)
            report["status"] = "refused"
            report["error"] = msg
            report["day_start_equity"] = store.get_day_start_equity(today)
            return report

    try:
        open_before = alpaca.get_open_orders()
        if flatten:
            alpaca.cancel_all_orders()
            if open_before:
                alpaca.wait_until_all_orders_clear(timeout_sec=8.0)
            report["orders_cancelled"] = len(open_before)
            logger.info("Cancelled %s open orders", len(open_before))
        else:
            # Resume: never cancel a working SELL — only stale BUY/stops
            n = alpaca.cancel_stale_non_sell_orders()
            report["orders_cancelled"] = n
            logger.info("Resume cancelled %s stale BUY/stop order(s)", n)
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
            leftover = alpaca.get_positions()
            if leftover:
                logger.error(
                    "Morning flatten still holding %s — retrying",
                    [p["symbol"] for p in leftover],
                )
                for pos in leftover:
                    try:
                        alpaca.close_position(pos["symbol"])
                        alpaca.wait_for_flat(pos["symbol"], timeout_sec=45.0)
                    except Exception as exc3:
                        logger.error("Flatten retry failed %s: %s", pos["symbol"], exc3)
                leftover = alpaca.get_positions()
                if leftover:
                    logger.error(
                        "PREPARE INCOMPLETE — still holding %s. "
                        "Do not start the day until flat, or inspect Alpaca.",
                        [p["symbol"] for p in leftover],
                    )
                    report["status"] = "incomplete"
                    report["still_holding"] = [p["symbol"] for p in leftover]
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

        leftover = alpaca.get_positions()
        if leftover:
            logger.error(
                "PREPARE INCOMPLETE — still holding %s",
                [p["symbol"] for p in leftover],
            )
            report["status"] = "incomplete"
            report["still_holding"] = [p["symbol"] for p in leftover]

    acct = alpaca.get_account()
    equity = acct["equity"]
    report["equity_after"] = equity

    if reset_day_baseline:
        store.set_day_start_equity(today, equity)
        report["day_start_equity"] = equity
    else:
        existing = store.get_day_start_equity(today)
        if existing is None:
            store.set_day_start_equity(today, equity)
            report["day_start_equity"] = equity
        else:
            report["day_start_equity"] = existing

    store.set_state(f"entries_blocked_{today.isoformat()}", "0")
    if flatten:
        # Morning clean start clears day-loss buy block; resume keeps it
        store.set_state(f"buys_blocked_day_loss_{today.isoformat()}", "0")
        store.clear_all_pending_sells()
    store.set_halted_today(today, False)
    store.log_activity(
        f"Session {report['mode']} | equity=${equity:,.2f} | "
        f"cancelled {report['orders_cancelled']} orders | "
        f"closed {len(report['positions_closed'])} positions | "
        f"day_start=${report['day_start_equity']:,.2f}",
        phase="prepare",
    )

    return report


def resume_session(
    alpaca: AlpacaClient | None = None,
    store: BotStore | None = None,
) -> dict:
    """After crash/outage: cancel stuck orders, keep positions and day P&L."""
    return prepare_clean_session(
        alpaca=alpaca, store=store, flatten=False, reset_day_baseline=False,
    )
