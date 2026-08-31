"""Order execution against Alpaca."""
from __future__ import annotations

import logging
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

    def execute(
        self,
        risk: RiskResult,
        cycle_id: int,
        decision_id: int,
        price: float,
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
            return {"id": "dry-run", "status": "simulated", "symbol": ticker}

        try:
            if action == "BUY":
                order = self.alpaca.submit_limit_order(
                    ticker, risk.qty, "BUY", limit_price=price * 1.002
                )
                if risk.action.stop:
                    try:
                        self.alpaca.submit_stop_order(ticker, risk.qty, risk.action.stop)
                    except Exception as exc:
                        logger.warning("Stop order failed for %s: %s", ticker, exc)
            elif action == "SELL":
                order = self.alpaca.submit_market_order(ticker, risk.qty, "SELL")
            else:
                return None

            self.store.save_order(
                cycle_id, ticker, action, risk.qty,
                alpaca_order_id=order.get("id"),
                status=order.get("status", "submitted"),
                decision_id=decision_id,
                filled_avg_price=order.get("filled_avg_price"),
            )
            return order
        except Exception as exc:
            logger.error("Order failed %s %s: %s", action, ticker, exc)
            self.store.save_order(
                cycle_id, ticker, action, risk.qty,
                alpaca_order_id=None, status=f"error:{exc}", decision_id=decision_id,
            )
            return None

    def ensure_stops(self, positions: list[dict[str, Any]], snapshots: dict[str, Any]) -> None:
        """Place protective stops if missing (best-effort)."""
        if self.dry_run:
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
                self.alpaca.submit_stop_order(sym, float(pos["qty"]), stop_px)
                logger.info("Placed missing stop for %s @ %s", sym, stop_px)
            except Exception as exc:
                logger.warning("Could not place stop for %s: %s", sym, exc)
