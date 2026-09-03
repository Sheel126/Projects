"""Order execution against Alpaca — idempotent sells / flatten."""
from __future__ import annotations

import logging
import time
from typing import Any

from finance_vibe.bot import config
from finance_vibe.bot.alpaca_client import AlpacaClient
from finance_vibe.bot.models import RiskResult
from finance_vibe.bot.store import BotStore

logger = logging.getLogger(__name__)

# Alpaca statuses that mean the order is still working (NOT filled)
_IN_FLIGHT = frozenset({
    "pending_new", "new", "accepted", "pending_replace", "pending_cancel",
    "partially_filled", "held", "calculated", "done_for_day",
})
_TERMINAL_OK = frozenset({"filled"})
_TERMINAL_BAD = frozenset({
    "canceled", "cancelled", "expired", "rejected", "replaced", "suspended",
})


def _status_norm(order: dict[str, Any]) -> str:
    return str(order.get("status", "")).lower().replace("orderstatus.", "")


class Executor:
    def __init__(
        self,
        alpaca: AlpacaClient | None = None,
        store: BotStore | None = None,
        dry_run: bool | None = None,
    ) -> None:
        self.alpaca = alpaca or AlpacaClient()
        self.store = store or BotStore()
        self.dry_run = config.DRY_RUN if dry_run is None else dry_run

    @staticmethod
    def _use_broker_stops() -> bool:
        if config.TRADING_MODE == "daily_active":
            return False
        return config.USE_BROKER_STOPS

    def _free_symbol_for_trade(self, symbol: str) -> None:
        """Cancel stale BUY/stops for this symbol only — never a working SELL."""
        n = self.alpaca.cancel_stale_non_sell_orders(timeout_sec=8.0, symbol=symbol)
        if n:
            logger.info("Freed %s: cancelled %s stale BUY/stop order(s)", symbol, n)

    def _submit_sell(self, ticker: str, qty: float) -> dict[str, Any]:
        """Idempotent exit: reuse open SELL, cancel-poll, sell remaining live qty.

        Safe to call repeatedly. Never stacks duplicate sells (held_for_orders).
        Never assumes cancel completed or that pending_new/new means filled.
        """
        ticker = ticker.upper()

        # 1) Active SELL already exists → reuse / monitor (do not cancel it)
        open_sells = self.alpaca.get_open_sell_orders(ticker)
        if open_sells:
            order = open_sells[0]
            logger.info(
                "Reusing open sell for %s id=%s status=%s (not duplicating)",
                ticker, order.get("id"), order.get("status"),
            )
            return order

        # 2) No position → noop
        live_qty = self.alpaca.get_position_qty(ticker)
        if live_qty <= 0:
            logger.info("No position to sell for %s — noop", ticker)
            return {"id": None, "status": "no_position", "symbol": ticker, "qty": 0.0}

        # 3) Cancel blocking orders → poll until clear, then re-check
        if self.alpaca.get_open_orders(ticker):
            cleared = self.alpaca.cancel_and_wait_clear(ticker, timeout_sec=8.0)
            open_sells = self.alpaca.get_open_sell_orders(ticker)
            if open_sells:
                return open_sells[0]
            if not cleared:
                logger.error(
                    "Sell blocked %s: orders still open after cancel timeout",
                    ticker,
                )
                raise RuntimeError(
                    f"Cannot sell {ticker}: open orders remain after cancel timeout"
                )

        # 4) Re-read remaining qty after cancels / partial fills
        live_qty = self.alpaca.get_position_qty(ticker)
        if live_qty <= 0:
            return {"id": None, "status": "no_position", "symbol": ticker, "qty": 0.0}

        sell_qty = min(float(qty), live_qty) if qty > 0 else live_qty

        # 5) Full close preferred; otherwise market sell remaining
        if sell_qty >= live_qty * 0.999:
            order = self.alpaca.close_position(ticker)
            status = _status_norm(order)
            if status == "no_position":
                return order
            if order.get("id") and status not in _TERMINAL_BAD:
                # Wait for flat, but do not treat pending_new/new as success forever
                flat = self.alpaca.wait_for_flat(ticker, timeout_sec=45.0)
                if not flat:
                    # Refresh order status if possible
                    try:
                        if order.get("id"):
                            order = self.alpaca.get_order(str(order["id"]))
                    except Exception as exc:
                        logger.warning("Order refresh after wait %s: %s", ticker, exc)
                    logger.warning(
                        "Sell still open for %s status=%s — will retry next cycle",
                        ticker, order.get("status"),
                    )
            return order

        return self.alpaca.submit_market_order(ticker, sell_qty, "SELL")

    def _sync_order(self, order_id: int, alpaca_order_id: str) -> dict[str, Any]:
        try:
            time.sleep(0.5)
            fresh = self.alpaca.get_order(alpaca_order_id)
            self.store.update_order_status(
                order_id,
                fresh.get("status", "unknown"),
                fresh.get("filled_avg_price"),
            )
            return fresh
        except Exception as exc:
            logger.warning("Order sync failed %s: %s", alpaca_order_id, exc)
            return {"status": "submitted", "id": alpaca_order_id}

    def execute(
        self,
        risk: RiskResult,
        cycle_id: int,
        decision_id: int,
        price: float,
        *,
        force_market_buy: bool = False,
    ) -> dict[str, Any] | None:
        if not risk.approved or risk.qty <= 0:
            return None

        action = risk.action.normalized_action()
        ticker = risk.action.ticker

        if self.dry_run:
            logger.info("DRY RUN %s %s qty=%s", action, ticker, risk.qty)
            self.store.save_order(
                cycle_id, ticker, action, risk.qty,
                alpaca_order_id="dry-run", status="simulated", decision_id=decision_id,
            )
            if action == "SELL":
                self.store.clear_pending_sell(ticker)
            return {"id": "dry-run", "status": "simulated", "symbol": ticker}

        try:
            if action == "BUY":
                if self.alpaca.get_open_sell_orders(ticker):
                    logger.warning(
                        "Skip BUY %s — working SELL still open (not doubling in)",
                        ticker,
                    )
                    return None
                self._free_symbol_for_trade(ticker)
                if force_market_buy:
                    order = self.alpaca.submit_market_order(ticker, risk.qty, "BUY")
                else:
                    order = self.alpaca.submit_limit_order(
                        ticker, risk.qty, "BUY", limit_price=price * 1.002,
                    )
            elif action == "SELL":
                order = self._submit_sell(ticker, risk.qty)
                if _status_norm(order) == "no_position":
                    self.store.clear_pending_sell(ticker)
                    logger.info("SELL %s skipped — already flat", ticker)
                    return order
            else:
                return None

            db_id = self.store.save_order(
                cycle_id, ticker, action, risk.qty,
                alpaca_order_id=order.get("id"),
                status=order.get("status", "submitted"),
                decision_id=decision_id,
                filled_avg_price=order.get("filled_avg_price"),
            )
            if order.get("id") and order.get("id") != "dry-run":
                order = self._sync_order(db_id, str(order["id"]))

            if action == "SELL":
                status = _status_norm(order)
                still_held = self.alpaca.get_position_qty(ticker) > 0
                if still_held:
                    # Any non-flat leftover must retry — never drop pending on unknown status
                    self.store.add_pending_sell(ticker)
                    logger.info(
                        "Sell leftover %s status=%s — pending retry until flat",
                        ticker, status,
                    )
                else:
                    self.store.clear_pending_sell(ticker)
            return order
        except Exception as exc:
            logger.error("Order failed %s %s: %s", action, ticker, exc)
            self.store.save_order(
                cycle_id, ticker, action, risk.qty,
                alpaca_order_id=None, status=f"error:{exc}", decision_id=decision_id,
            )
            if action == "SELL":
                self.store.add_pending_sell(ticker)
            return None

    def retry_pending_sells(
        self,
        positions: list[dict[str, Any]],
        cycle_id: int,
    ) -> int:
        pending = self.store.get_pending_sell_symbols()
        if not pending:
            return 0

        pos_map = {p["symbol"].upper(): p for p in positions}
        retried = 0
        for sym in pending:
            pos = pos_map.get(sym.upper())
            if not pos:
                self.store.clear_pending_sell(sym)
                continue
            qty = float(pos["qty"])
            if qty <= 0:
                self.store.clear_pending_sell(sym)
                continue
            try:
                order = self._submit_sell(sym, qty)
                status = _status_norm(order)
                if status == "no_position":
                    self.store.clear_pending_sell(sym)
                    continue
                self.store.save_order(
                    cycle_id, sym, "SELL", qty,
                    alpaca_order_id=order.get("id"),
                    status=order.get("status", "retry_submitted"),
                )
                still_held = self.alpaca.get_position_qty(sym) > 0
                if still_held:
                    logger.info(
                        "Retried sell %s still open status=%s",
                        sym, status,
                    )
                else:
                    self.store.clear_pending_sell(sym)
                retried += 1
                logger.info("Retried sell %s qty=%s status=%s", sym, qty, order.get("status"))
            except Exception as exc:
                logger.error("Retry sell failed %s: %s", sym, exc)
        return retried

    def flatten_positions(self, positions: list[dict[str, Any]], cycle_id: int) -> int:
        """Idempotent flatten — safe to call multiple times. Logs COMPLETE / FAILED."""
        closed = 0
        failed: list[str] = []
        in_flight: list[str] = []

        for pos in positions:
            sym = pos["symbol"]
            qty = float(pos["qty"])
            if qty <= 0:
                continue
            try:
                # Always use live remaining qty (partial fills may have reduced)
                live_qty = self.alpaca.get_position_qty(sym)
                if live_qty <= 0:
                    self.store.clear_pending_sell(sym)
                    continue

                order = self._submit_sell(sym, live_qty)
                status = _status_norm(order)
                if status == "no_position":
                    self.store.clear_pending_sell(sym)
                    closed += 1
                    continue

                self.store.save_order(
                    cycle_id, sym, "SELL", live_qty,
                    alpaca_order_id=order.get("id"),
                    status=order.get("status", "eod_flat"),
                )

                still_held = self.alpaca.get_position_qty(sym) > 0
                if not still_held:
                    self.store.clear_pending_sell(sym)
                    closed += 1
                    logger.info("EOD flatten %s flat status=%s", sym, status)
                elif status in _IN_FLIGHT or order.get("id"):
                    self.store.add_pending_sell(sym)
                    in_flight.append(sym)
                    logger.warning(
                        "EOD flatten %s in-flight status=%s — pending",
                        sym, status,
                    )
                else:
                    self.store.add_pending_sell(sym)
                    failed.append(sym)
                    logger.error("EOD flatten failed %s status=%s", sym, status)
            except Exception as exc:
                logger.error("EOD flatten failed %s: %s", sym, exc)
                self.store.add_pending_sell(sym)
                failed.append(sym)

        remaining = [
            p["symbol"] for p in self.alpaca.get_positions() if float(p.get("qty", 0)) > 0
        ]
        if not remaining:
            logger.info("EOD FLAT COMPLETE — book is flat")
        else:
            logger.error(
                "EOD FLAT FAILED — still holding %s (failed=%s in_flight=%s)",
                remaining, failed, in_flight,
            )
        return closed

    def ensure_stops(self, positions: list[dict[str, Any]], snapshots: dict[str, Any]) -> None:
        if self.dry_run or not self._use_broker_stops():
            return
        for pos in positions:
            sym = pos["symbol"]
            open_stops = [
                o for o in self.alpaca.get_open_orders(sym)
                if "stop" in str(o.get("type", "")).lower()
            ]
            if open_stops:
                continue
            snap = snapshots.get(sym)
            stop_px = None
            if snap:
                stop_px = getattr(snap, "tight_stop", None) or getattr(snap, "stop", None)
            if not stop_px:
                continue
            try:
                stop_qty = max(1, int(float(pos["qty"])))
                self.alpaca.submit_stop_order(sym, stop_qty, stop_px)
                logger.info("Placed missing stop for %s qty=%s @ %s", sym, stop_qty, stop_px)
            except Exception as exc:
                logger.warning("Could not place stop for %s: %s", sym, exc)
