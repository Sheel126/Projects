"""Alpaca Markets API wrapper for paper trading."""
from __future__ import annotations

import logging
import time as time_mod
from datetime import datetime, timedelta, time
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from finance_vibe.bot import config

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
MARKET_OPEN_TIME = time(9, 30)


class AlpacaClient:
    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or config.ALPACA_API_KEY
        self.secret_key = secret_key or config.ALPACA_SECRET_KEY
        self.base_url = base_url or config.ALPACA_BASE_URL
        self._trading = None
        self._data = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.secret_key)

    def _ensure_clients(self) -> None:
        if self._trading is not None:
            return
        if not self.configured:
            raise RuntimeError(
                "Alpaca API keys missing. Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env"
            )
        from alpaca.trading.client import TradingClient
        from alpaca.data.historical import StockHistoricalDataClient

        paper = "paper" in self.base_url.lower()
        self._trading = TradingClient(
            self.api_key, self.secret_key, paper=paper, url_override=self.base_url
        )
        self._data = StockHistoricalDataClient(self.api_key, self.secret_key)

    def get_account(self) -> dict[str, Any]:
        self._ensure_clients()
        acct = self._trading.get_account()
        return {
            "equity": float(acct.equity),
            "cash": float(acct.cash),
            "buying_power": float(acct.buying_power),
            "portfolio_value": float(acct.portfolio_value),
            "status": str(acct.status),
        }

    def get_positions(self) -> list[dict[str, Any]]:
        self._ensure_clients()
        positions = self._trading.get_all_positions()
        out = []
        for p in positions:
            qty = float(p.qty)
            avg = float(p.avg_entry_price)
            cur = float(p.current_price)
            pnl_pct = ((cur - avg) / avg * 100) if avg else 0.0
            out.append({
                "symbol": p.symbol,
                "qty": qty,
                "avg_entry_price": avg,
                "current_price": cur,
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc) * 100,
                "pnl_pct": pnl_pct,
                "side": p.side,
            })
        return out

    def get_latest_prices(self, symbols: list[str]) -> dict[str, dict[str, float]]:
        self._ensure_clients()
        from alpaca.data.requests import StockLatestQuoteRequest, StockSnapshotRequest

        symbols = [s.upper() for s in symbols]
        prices: dict[str, dict[str, float]] = {}

        try:
            snaps = self._data.get_stock_snapshot(
                StockSnapshotRequest(symbol_or_symbols=symbols)
            )
            if not isinstance(snaps, dict):
                snaps = {symbols[0]: snaps}
            for sym, snap in snaps.items():
                bar = snap.daily_bar
                quote = snap.latest_quote
                trade = snap.latest_trade
                price = float(trade.price) if trade else (
                    (float(quote.bid_price) + float(quote.ask_price)) / 2
                    if quote and quote.bid_price and quote.ask_price else 0.0
                )
                prev_close = float(bar.close) if bar else price
                open_px = float(bar.open) if bar else price
                change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0.0
                change_open = ((price - open_px) / open_px * 100) if open_px else 0.0
                prices[sym] = {
                    "price": price,
                    "prev_close": prev_close,
                    "open": open_px,
                    "change_pct": change_pct,
                    "change_from_open_pct": change_open,
                }
        except Exception as exc:
            logger.warning("Snapshot fetch failed, trying quotes: %s", exc)
            quotes = self._data.get_stock_latest_quote(
                StockLatestQuoteRequest(symbol_or_symbols=symbols)
            )
            if not isinstance(quotes, dict):
                quotes = {symbols[0]: quotes}
            for sym, q in quotes.items():
                bid = float(q.bid_price or 0)
                ask = float(q.ask_price or 0)
                price = (bid + ask) / 2 if bid and ask else bid or ask
                prices[sym] = {
                    "price": price,
                    "prev_close": price,
                    "open": price,
                    "change_pct": 0.0,
                    "change_from_open_pct": 0.0,
                }
        return prices

    def get_intraday_bars(self, symbol: str, minutes: int = 390) -> pd.DataFrame:
        """Today's 1-minute bars from market open (for VWAP / IBS / ORB)."""
        self._ensure_clients()
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        today = datetime.now(ET).date()
        start = datetime.combine(today, MARKET_OPEN_TIME, tzinfo=ET)
        end = datetime.now(ET)
        if end < start:
            return pd.DataFrame()

        req = StockBarsRequest(
            symbol_or_symbols=symbol.upper(),
            timeframe=TimeFrame(amount=1, unit=TimeFrameUnit.Minute),
            start=start,
            end=end,
            feed="iex",
        )
        try:
            bars = self._data.get_stock_bars(req)
        except Exception as exc:
            logger.warning("Intraday bars failed %s: %s", symbol, exc)
            return pd.DataFrame()

        sym = symbol.upper()
        if sym not in bars.data or not bars.data[sym]:
            return pd.DataFrame()

        rows = []
        for b in bars.data[sym]:
            rows.append({
                "Timestamp": pd.Timestamp(b.timestamp).tz_convert(ET),
                "Open": float(b.open),
                "High": float(b.high),
                "Low": float(b.low),
                "Close": float(b.close),
                "Volume": float(b.volume),
            })
        return pd.DataFrame(rows).sort_values("Timestamp").reset_index(drop=True)

    def get_daily_bars(self, symbol: str, days: int = 150) -> pd.DataFrame:
        self._ensure_clients()
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        end = datetime.now(ET)
        start = end - timedelta(days=days + 30)
        req = StockBarsRequest(
            symbol_or_symbols=symbol.upper(),
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed="iex",
        )
        bars = self._data.get_stock_bars(req)
        sym = symbol.upper()
        if sym not in bars.data or not bars.data[sym]:
            return pd.DataFrame()
        rows = []
        for b in bars.data[sym]:
            rows.append({
                "Date": pd.Timestamp(b.timestamp).tz_convert(ET).normalize(),
                "Open": float(b.open),
                "High": float(b.high),
                "Low": float(b.low),
                "Close": float(b.close),
                "Volume": float(b.volume),
            })
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        return df.sort_values("Date").reset_index(drop=True)

    def submit_stop_order(
        self, symbol: str, qty: float, stop_price: float
    ) -> dict[str, Any]:
        """Protective stop — whole shares + DAY (Alpaca rejects fractional GTC stops)."""
        self._ensure_clients()
        from alpaca.trading.requests import StopOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        whole_qty = max(1, int(qty))
        req = StopOrderRequest(
            symbol=symbol.upper(),
            qty=whole_qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            stop_price=round(stop_price, 2),
        )
        order = self._trading.submit_order(req)
        return self._order_dict(order)

    def submit_market_order(self, symbol: str, qty: float, side: str) -> dict[str, Any]:
        self._ensure_clients()
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
        # Buys: prefer whole shares; sells: allow fractional to fully exit
        if side.upper() == "BUY":
            order_qty = max(1, int(qty))
        else:
            order_qty = round(qty, 4)
            if order_qty == int(order_qty):
                order_qty = int(order_qty)
        req = MarketOrderRequest(
            symbol=symbol.upper(),
            qty=order_qty,
            side=order_side,
            time_in_force=TimeInForce.DAY,
        )
        order = self._trading.submit_order(req)
        return self._order_dict(order)

    def submit_limit_order(
        self, symbol: str, qty: float, side: str, limit_price: float
    ) -> dict[str, Any]:
        self._ensure_clients()
        from alpaca.trading.requests import LimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
        if side.upper() == "BUY":
            order_qty = max(1, int(qty))
        else:
            order_qty = round(qty, 4)
            if order_qty == int(order_qty):
                order_qty = int(order_qty)
        req = LimitOrderRequest(
            symbol=symbol.upper(),
            qty=order_qty,
            side=order_side,
            time_in_force=TimeInForce.DAY,
            limit_price=round(limit_price, 2),
        )
        order = self._trading.submit_order(req)
        return self._order_dict(order)

    def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        self._ensure_clients()
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        req = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        orders = self._trading.get_orders(req)
        out = [self._order_dict(o) for o in orders]
        if symbol:
            out = [o for o in out if o["symbol"] == symbol.upper()]
        return out

    def get_open_sell_orders(self, symbol: str) -> list[dict[str, Any]]:
        """Open SELL orders for a symbol (any status that still locks shares)."""
        symbol = symbol.upper()
        return [
            o for o in self.get_open_orders(symbol)
            if "SELL" in str(o.get("side", "")).upper()
        ]

    def wait_until_orders_clear(
        self,
        symbol: str,
        timeout_sec: float = 5.0,
        poll_sec: float = 0.25,
    ) -> bool:
        """Poll until no open orders remain for symbol. Never assume cancel completed."""
        symbol = symbol.upper()
        deadline = time_mod.time() + timeout_sec
        while time_mod.time() < deadline:
            if not self.get_open_orders(symbol):
                return True
            time_mod.sleep(poll_sec)
        return not self.get_open_orders(symbol)

    def cancel_orders_for_symbol(
        self,
        symbol: str,
        wait_sec: float = 1.0,
        *,
        until_clear: bool = False,
        timeout_sec: float = 5.0,
    ) -> int:
        """Cancel all open orders for one symbol (frees shares for market sell).

        When until_clear=True, poll until orders are gone or timeout — a cancel
        request alone does not mean the order is clear.
        """
        self._ensure_clients()
        symbol = symbol.upper()
        orders = self.get_open_orders(symbol)
        for o in orders:
            try:
                self._trading.cancel_order_by_id(o["id"])
            except Exception as exc:
                logger.warning("Cancel order %s %s: %s", symbol, o.get("id"), exc)
        if not orders:
            return 0
        if until_clear:
            cleared = self.wait_until_orders_clear(symbol, timeout_sec=timeout_sec)
            if not cleared:
                remaining = self.get_open_orders(symbol)
                logger.error(
                    "Cancel timeout %s: %s order(s) still open after %.1fs",
                    symbol, len(remaining), timeout_sec,
                )
            return len(orders)
        if wait_sec > 0:
            time_mod.sleep(wait_sec)
        return len(orders)

    def cancel_and_wait_clear(self, symbol: str, timeout_sec: float = 5.0) -> bool:
        """Cancel all open orders for symbol and poll until clear. Returns True if clear."""
        self.cancel_orders_for_symbol(
            symbol, wait_sec=0, until_clear=True, timeout_sec=timeout_sec,
        )
        return not self.get_open_orders(symbol.upper())

    def wait_for_flat(self, symbol: str, timeout_sec: float = 30.0) -> bool:
        """Wait until no position remains for symbol."""
        symbol = symbol.upper()
        deadline = time_mod.time() + timeout_sec
        while time_mod.time() < deadline:
            if not any(p["symbol"] == symbol for p in self.get_positions()):
                return True
            time_mod.sleep(1.0)
        return not any(p["symbol"] == symbol for p in self.get_positions())

    def get_position_qty(self, symbol: str) -> float:
        """Live remaining qty for symbol (0 if flat)."""
        symbol = symbol.upper()
        for p in self.get_positions():
            if p["symbol"] == symbol:
                return float(p["qty"])
        return 0.0

    def close_position(self, symbol: str) -> dict[str, Any]:
        """Close entire position — idempotent: reuse open SELL, cancel-poll, then one sell.

        Never assumes cancel succeeded. Re-reads live qty after cancels/partial fills.
        """
        self._ensure_clients()
        symbol = symbol.upper()

        existing_sells = self.get_open_sell_orders(symbol)
        if existing_sells:
            logger.info(
                "close_position %s: reusing open SELL %s status=%s",
                symbol, existing_sells[0].get("id"), existing_sells[0].get("status"),
            )
            return existing_sells[0]

        live_qty = self.get_position_qty(symbol)
        if live_qty <= 0:
            return {"id": None, "status": "no_position", "symbol": symbol, "qty": 0.0}

        if self.get_open_orders(symbol):
            cleared = self.cancel_and_wait_clear(symbol, timeout_sec=5.0)
            # Re-check for a SELL that may still be open after partial cancel
            existing_sells = self.get_open_sell_orders(symbol)
            if existing_sells:
                return existing_sells[0]
            if not cleared:
                raise RuntimeError(
                    f"Cannot close {symbol}: open orders remain after cancel timeout"
                )

        live_qty = self.get_position_qty(symbol)
        if live_qty <= 0:
            return {"id": None, "status": "no_position", "symbol": symbol, "qty": 0.0}

        order = self._trading.close_position(symbol)
        return self._order_dict(order)

    def close_all_positions(self) -> list[dict[str, Any]]:
        """Flatten book — one symbol at a time; safe to call repeatedly."""
        closed: list[dict[str, Any]] = []
        for pos in list(self.get_positions()):
            sym = pos["symbol"]
            try:
                order = self.close_position(sym)
                status = str(order.get("status", "")).lower()
                if status == "no_position":
                    continue
                # Wait for flat only when we have an order in flight or just submitted
                if order.get("id"):
                    self.wait_for_flat(sym, timeout_sec=45.0)
                closed.append({"symbol": sym, "qty": pos["qty"], "order": order})
            except Exception as exc:
                logger.error("close_position failed %s: %s", sym, exc)
                raise
        return closed

    def flatten_all_positions(self) -> list[dict[str, Any]]:
        """Market-sell every open position."""
        return self.close_all_positions()

    def cancel_all_orders(self) -> None:
        self._ensure_clients()
        self._trading.cancel_orders()

    def cancel_open_buy_orders(self) -> int:
        """Cancel all open BUY orders (late session / cleanup)."""
        cancelled = 0
        for o in self.get_open_orders():
            if "BUY" in str(o.get("side", "")).upper():
                try:
                    self._trading.cancel_order_by_id(o["id"])
                    cancelled += 1
                except Exception as exc:
                    logger.warning("Cancel buy order %s: %s", o.get("id"), exc)
        return cancelled

    def get_order(self, order_id: str) -> dict[str, Any]:
        self._ensure_clients()
        order = self._trading.get_order_by_id(order_id)
        return self._order_dict(order)

    @staticmethod
    def _normalize_status(status: Any) -> str:
        s = str(status)
        return s.replace("OrderStatus.", "").lower()

    @staticmethod
    def _order_dict(order: Any) -> dict[str, Any]:
        status = AlpacaClient._normalize_status(order.status)
        filled_qty = getattr(order, "filled_qty", None)
        return {
            "id": str(order.id),
            "symbol": order.symbol,
            "qty": float(order.qty) if order.qty else 0.0,
            "filled_qty": float(filled_qty) if filled_qty is not None else 0.0,
            "side": str(order.side).replace("OrderSide.", ""),
            "type": str(order.type).replace("OrderType.", ""),
            "status": status,
            "filled_avg_price": float(order.filled_avg_price or 0),
            "limit_price": float(order.limit_price or 0) if order.limit_price else None,
            "stop_price": float(order.stop_price or 0) if order.stop_price else None,
        }
