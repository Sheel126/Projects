"""Shared dataclasses for the trading bot."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TradeAction:
    ticker: str
    action: str  # BUY | SELL | HOLD
    pct: float = 0.0  # % of equity for BUY, % of position for SELL
    stop: float | None = None
    reason: str = ""

    def normalized_action(self) -> str:
        return self.action.strip().upper()


@dataclass
class AgentDecision:
    actions: list[TradeAction] = field(default_factory=list)
    summary: str = ""
    raw_response: str = ""
    model: str = ""
    used_fallback: bool = False


@dataclass
class TickerSnapshot:
    ticker: str
    price: float
    change_pct: float
    change_from_open_pct: float
    rsi: float | None
    ema20: float | None
    ema50: float | None
    atr: float | None
    setup_type: str | None
    setup_notes: str | None
    entry: float | None
    stop: float | None
    target1: float | None
    target2: float | None
    vs_qqq_pct: float | None
    regime_ok: bool | None
    in_position: bool = False
    position_qty: float = 0.0
    position_pnl_pct: float | None = None
    # Finance-Vibe extended signals
    vibe_score: int | None = None
    vibe_sentiment: str | None = None
    vibe_action: str | None = None
    coiled_cobra_score: float | None = None
    coiled_cobra_grade: str | None = None
    coiled_cobra_checks: str | None = None
    ml_pred_return: float | None = None
    ml_rank: int | None = None
    conviction: float = 0.0
    signal_sources: list[str] = field(default_factory=list)
    rs_63d: float | None = None
    has_open_buy_order: bool = False
    has_open_sell_order: bool = False
    sector: str | None = None
    active_score: float = 0.0
    tight_stop: float | None = None
    vwap: float | None = None
    price_vs_vwap_pct: float | None = None
    ibs: float | None = None
    orb_signal: str | None = None
    day_high: float | None = None
    day_low: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "price": self.price,
            "change_pct": round(self.change_pct, 3),
            "change_from_open_pct": round(self.change_from_open_pct, 3),
            "rsi": self.rsi,
            "ema20": self.ema20,
            "ema50": self.ema50,
            "atr": self.atr,
            "setup_type": self.setup_type,
            "setup_notes": self.setup_notes,
            "entry": self.entry,
            "stop": self.stop,
            "target1": self.target1,
            "target2": self.target2,
            "vs_qqq_pct": self.vs_qqq_pct,
            "regime_ok": self.regime_ok,
            "rs_63d": self.rs_63d,
            "in_position": self.in_position,
            "position_qty": self.position_qty,
            "position_pnl_pct": self.position_pnl_pct,
            "vibe_score": self.vibe_score,
            "vibe_sentiment": self.vibe_sentiment,
            "vibe_action": self.vibe_action,
            "coiled_cobra_score": self.coiled_cobra_score,
            "coiled_cobra_grade": self.coiled_cobra_grade,
            "coiled_cobra_checks": self.coiled_cobra_checks,
            "ml_pred_return": self.ml_pred_return,
            "ml_rank": self.ml_rank,
            "conviction": self.conviction,
            "signal_sources": self.signal_sources,
            "has_open_buy_order": self.has_open_buy_order,
            "has_open_sell_order": self.has_open_sell_order,
            "sector": self.sector,
            "active_score": self.active_score,
            "tight_stop": self.tight_stop,
            "vwap": self.vwap,
            "price_vs_vwap_pct": self.price_vs_vwap_pct,
            "ibs": self.ibs,
            "orb_signal": self.orb_signal,
            "day_high": self.day_high,
            "day_low": self.day_low,
        }


@dataclass
class CycleContext:
    account_equity: float
    account_cash: float
    buying_power: float
    day_pnl_pct: float
    halted: bool
    watchlist: list[TickerSnapshot]
    open_positions: list[dict[str, Any]]
    strategy_notes: str
    benchmark_change_pct: float | None = None
    open_orders: list[dict[str, Any]] = field(default_factory=list)
    market_regime: dict[str, Any] = field(default_factory=dict)
    conviction_ranking: list[dict[str, Any]] = field(default_factory=list)
    trading_mode: str = "daily_active"

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "account": {
                "equity": round(self.account_equity, 2),
                "cash": round(self.account_cash, 2),
                "buying_power": round(self.buying_power, 2),
                "day_pnl_pct": round(self.day_pnl_pct, 3),
                "halted": self.halted,
            },
            "market_regime": self.market_regime,
            "benchmark_change_pct": self.benchmark_change_pct,
            "conviction_ranking": self.conviction_ranking,
            "open_positions": self.open_positions,
            "open_orders": self.open_orders,
            "watchlist": [t.to_dict() for t in self.watchlist],
            "strategy_notes": self.strategy_notes,
            "trading_mode": self.trading_mode,
        }


@dataclass
class RiskResult:
    approved: bool
    action: TradeAction
    qty: float = 0.0
    notional: float = 0.0
    notes: str = ""
