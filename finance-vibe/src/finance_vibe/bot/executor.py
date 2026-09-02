"""Order execution against Alpaca."""
from __future__ import annotations

import logging
import time
from typing import Any

from finance_vibe.bot import config
from finance_vibe.bot.alpaca_client import AlpacaClient
from finance_vibe.bot.models import RiskResult
from finance_vibe.bot.store import BotStore

logger = logging.getLogger(__name__)


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
        n = self.alpaca.cancel_orders_for_symbol(symbol, wait_sec=2.0)
        if n:
            logger.info("Freed %s: cancelled %s open order(s)", symbol, n)

    def _submit_sell(self, ticker: str, qty: float) -> dict[str, Any]:
        """Exit via close_position — never stack duplicate sells (held_for_orders)."""
        ticker = ticker.upper()
        self._free_symbol_for_trade(ticker)

        open_sells = [
            o for o in self.alpaca.get_open_orders(ticker)
            if "SELL" in str(o.get("side", "")).upper()
        ]
        if open_sells:
            logger.info("Reusing open sell for %s (not duplicating)", ticker)
            return open_sells[0]

        positions = self.alpaca.get_positions()
        pos = next((p for p in positions if p["symbol"] == ticker), None)
        if not pos:
            raise RuntimeError(f"No position to sell for {ticker}")

        pos_qty = float(pos["qty"])
        if qty >= pos_qty * 0.999:
            order = self.alpaca.close_position(ticker)
            self.alpaca.wait_for_flat(ticker, timeout_sec=45.0)
            return order
        return self.alpaca.submit_market_order(ticker, qty, "SELL")

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
                self._free_symbol_for_trade(ticker)
                if force_market_buy:
                    order = self.alpaca.submit_market_order(ticker, risk.qty, "BUY")
                else:
                    order = self.alpaca.submit_limit_order(
                        ticker, risk.qty, "BUY", limit_price=price * 1.002,
                    )
            elif action == "SELL":
                order = self._submit_sell(ticker, risk.qty)
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
                status = str(order.get("status", "")).lower()
                if "error" in status or "rejected" in status:
                    self.store.add_pending_sell(ticker)
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
                self.store.save_order(
                    cycle_id, sym, "SELL", qty,
                    alpaca_order_id=order.get("id"),
                    status=order.get("status", "retry_submitted"),
                )
                self.store.clear_pending_sell(sym)
                retried += 1
                logger.info("Retried sell %s qty=%s status=%s", sym, qty, order.get("status"))
            except Exception as exc:
                logger.error("Retry sell failed %s: %s", sym, exc)
        return retried

    def flatten_positions(self, positions: list[dict[str, Any]], cycle_id: int) -> int:
        closed = 0
        for pos in positions:
            sym = pos["symbol"]
            qty = float(pos["qty"])
            if qty <= 0:
                continue
            try:
                order = self._submit_sell(sym, qty)
                self.store.save_order(
                    cycle_id, sym, "SELL", qty,
                    alpaca_order_id=order.get("id"),
                    status=order.get("status", "eod_flat"),
                )
                self.store.clear_pending_sell(sym)
                closed += 1
                logger.info("EOD flatten %s qty=%s", sym, qty)
            except Exception as exc:
                logger.error("EOD flatten failed %s: %s", sym, exc)
                self.store.add_pending_sell(sym)
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
