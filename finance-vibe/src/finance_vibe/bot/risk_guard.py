"""Hard risk limits — LLM cannot override."""
from __future__ import annotations

from finance_vibe.bot import config
from finance_vibe.bot.models import CycleContext, RiskResult, TradeAction, TickerSnapshot


class RiskGuard:
    def __init__(
        self,
        risk_per_trade_pct: float | None = None,
        max_positions: int | None = None,
        max_position_pct: float | None = None,
        min_notional: float | None = None,
    ) -> None:
        self.risk_pct = risk_per_trade_pct or config.RISK_PER_TRADE_PCT
        self.max_positions = max_positions or config.MAX_POSITIONS
        self.max_position_pct = max_position_pct or config.MAX_POSITION_PCT
        self.min_notional = min_notional or config.MIN_ORDER_NOTIONAL

    def validate(
        self,
        action: TradeAction,
        ctx: CycleContext,
        snapshot: TickerSnapshot | None,
        open_position_count: int,
    ) -> RiskResult:
        act = action.normalized_action()
        ticker = action.ticker.upper()

        if act == "HOLD":
            return RiskResult(True, action, notes="HOLD")

        if ctx.halted and act == "BUY":
            return RiskResult(False, action, notes="Daily loss halt — no new buys")

        if act == "SELL":
            if not snapshot or not snapshot.in_position or snapshot.position_qty <= 0:
                return RiskResult(False, action, notes="No position to sell")
            sell_pct = max(0.0, min(100.0, action.pct)) / 100.0
            if sell_pct <= 0:
                sell_pct = 1.0
            qty = snapshot.position_qty * sell_pct
            notional = qty * snapshot.price
            if notional < 1.0 and qty < snapshot.position_qty:
                return RiskResult(False, action, notes="Sell size too small")
            return RiskResult(
                True, action, qty=round(qty, 4), notional=round(notional, 2),
                notes=f"SELL {sell_pct*100:.0f}% of position",
            )

        if act == "BUY":
            if snapshot and snapshot.in_position:
                return RiskResult(False, action, notes="Already in position")
            if open_position_count >= self.max_positions:
                return RiskResult(False, action, notes=f"Max {self.max_positions} positions")

            price = snapshot.price if snapshot else 0.0
            if price <= 0:
                return RiskResult(False, action, notes="Invalid price")

            stop = action.stop or (snapshot.tight_stop if snapshot else None)
            if stop is None and snapshot and snapshot.stop:
                stop = snapshot.stop
            if stop is None and snapshot and snapshot.atr:
                stop = round(price - 1.5 * snapshot.atr, 2)
            if stop is None or stop >= price:
                return RiskResult(False, action, notes="BUY requires valid stop below price")

            deploy_pct = max(0.0, min(100.0, action.pct)) / 100.0
            if deploy_pct <= 0:
                deploy_pct = self.risk_pct * 3  # default ~9% if LLM sends 0
            deploy_pct = min(deploy_pct, self.max_position_pct)

            notional = ctx.account_equity * deploy_pct
            notional = min(notional, ctx.account_cash * 0.98)
            if notional < self.min_notional:
                return RiskResult(False, action, notes=f"Below min notional ${self.min_notional}")

            risk_per_share = price - stop
            if risk_per_share <= 0:
                return RiskResult(False, action, notes="Invalid risk per share")

            risk_budget = ctx.account_equity * self.risk_pct
            qty_by_risk = risk_budget / risk_per_share
            qty_by_notional = notional / price
            qty = min(qty_by_risk, qty_by_notional)
            notional = qty * price

            if notional < self.min_notional:
                return RiskResult(False, action, notes="Sized order below minimum")

            approved_action = TradeAction(
                ticker=ticker, action="BUY", pct=deploy_pct * 100,
                stop=stop, reason=action.reason,
            )
            return RiskResult(
                True, approved_action,
                qty=round(qty, 4), notional=round(notional, 2),
                notes=f"BUY ${notional:.0f} @ ~{price}, stop {stop}",
            )

        return RiskResult(False, action, notes=f"Unknown action: {act}")

    def check_daily_halt(
        self, day_start_equity: float, current_equity: float
    ) -> tuple[bool, float]:
        if day_start_equity <= 0:
            return False, 0.0
        pnl_pct = (current_equity - day_start_equity) / day_start_equity
        halted = pnl_pct <= -config.DAILY_LOSS_HALT_PCT
        return halted, pnl_pct * 100
