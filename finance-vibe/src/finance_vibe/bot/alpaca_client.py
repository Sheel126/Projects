"""Alpaca Markets API wrapper for paper trading."""
from __future__ import annotations

import logging
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

    def submit_market_order(self, symbol: str, qty: float, side: str) -> dict[str, Any]:
        self._ensure_clients()
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
        req = MarketOrderRequest(
            symbol=symbol.upper(),
            qty=round(qty, 4),
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
        req = LimitOrderRequest(
            symbol=symbol.upper(),
            qty=round(qty, 4),
            side=order_side,
            time_in_force=TimeInForce.DAY,
            limit_price=round(limit_price, 2),
        )
        order = self._trading.submit_order(req)
        return self._order_dict(order)

    def submit_stop_order(
        self, symbol: str, qty: float, stop_price: float
    ) -> dict[str, Any]:
        self._ensure_clients()
        from alpaca.trading.requests import StopOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        req = StopOrderRequest(
            symbol=symbol.upper(),
            qty=round(qty, 4),
            side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC,
            stop_price=round(stop_price, 2),
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

    def cancel_all_orders(self) -> None:
        self._ensure_clients()
        self._trading.cancel_orders()

    @staticmethod
    def _order_dict(order: Any) -> dict[str, Any]:
        return {
            "id": str(order.id),
            "symbol": order.symbol,
            "qty": float(order.qty) if order.qty else 0.0,
            "side": str(order.side),
            "type": str(order.type),
            "status": str(order.status),
            "filled_avg_price": float(order.filled_avg_price or 0),
            "limit_price": float(order.limit_price or 0) if order.limit_price else None,
            "stop_price": float(order.stop_price or 0) if order.stop_price else None,
        }
