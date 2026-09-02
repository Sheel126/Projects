"""Hard risk limits — LLM cannot override."""
from __future__ import annotations

import math

from finance_vibe.bot import config
from finance_vibe.bot.market_hours import is_late_entry_window, is_market_open
from finance_vibe.bot.models import CycleContext, RiskResult, TradeAction, TickerSnapshot
from finance_vibe.bot.regime import benchmark_blocks_new_buys


def _whole_shares(qty: float) -> int:
    """Alpaca rejects fractional GTC stops — size buys in whole shares."""
    return max(0, int(math.floor(qty + 1e-9)))


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

        if (ctx.halted or getattr(ctx, "entries_blocked", False)) and act == "BUY":
            return RiskResult(
                False, action,
                notes="Entries blocked (halt, day-loss, regime, or EOD) — no new buys",
            )

        if act == "BUY":
            if not is_market_open():
                return RiskResult(False, action, notes="Market not open — no buys")
            if is_late_entry_window():
                return RiskResult(False, action, notes="Late session — no new buys after 3:30 PM")
            if benchmark_blocks_new_buys(ctx.benchmark_change_from_open_pct):
                chg = ctx.benchmark_change_from_open_pct
                return RiskResult(
                    False, action,
                    notes=(
                        f"{config.BENCHMARK} red from open "
                        f"({chg:.2f}% <= {config.BENCHMARK_BLOCK_PCT}%) — dip buys blocked"
                    ),
                )

        if act == "SELL":
            if not snapshot or not snapshot.in_position or snapshot.position_qty <= 0:
                return RiskResult(False, action, notes="No position to sell")
            sell_pct = max(0.0, min(100.0, action.pct)) / 100.0
            if sell_pct <= 0:
                sell_pct = 1.0
            if sell_pct >= 0.999:
                qty = float(snapshot.position_qty)
            else:
                qty = float(_whole_shares(snapshot.position_qty * sell_pct))
                if qty < 1:
                    qty = float(snapshot.position_qty)
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
                deploy_pct = self.risk_pct * 3
            deploy_pct = min(deploy_pct, self.max_position_pct)
            # Day-loss caution: no size increase above baseline active position %
            if self.day_loss_caution(ctx.day_pnl_pct):
                baseline = config.ACTIVE_POSITION_PCT / 100.0
                deploy_pct = min(deploy_pct, baseline)

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
            raw_qty = min(qty_by_risk, qty_by_notional)

            if config.WHOLE_SHARES_ONLY:
                qty = float(_whole_shares(raw_qty))
                if qty < 1:
                    return RiskResult(False, action, notes="Sized below 1 whole share")
            else:
                qty = raw_qty

            notional = qty * price
            if notional < self.min_notional:
                return RiskResult(False, action, notes="Sized order below minimum")

            approved_action = TradeAction(
                ticker=ticker, action="BUY", pct=deploy_pct * 100,
                stop=stop, reason=action.reason,
            )
            return RiskResult(
                True, approved_action,
                qty=round(qty, 4) if not config.WHOLE_SHARES_ONLY else qty,
                notional=round(notional, 2),
                notes=f"BUY {int(qty) if config.WHOLE_SHARES_ONLY else qty} sh @ ~{price}, stop {stop}",
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

    def day_loss_caution(self, day_pnl_pct: float) -> bool:
        """Soft breaker: day PnL at/below caution threshold (e.g. -0.5%)."""
        return day_pnl_pct <= config.DAY_CAUTION_PCT

    def day_loss_blocks_buys(self, day_pnl_pct: float) -> bool:
        """Hard breaker: stop NEW buys for rest of session (e.g. -1.0%). Sells/EOD still OK."""
        return day_pnl_pct <= config.DAY_BLOCK_BUYS_PCT
