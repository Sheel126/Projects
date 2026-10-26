"""The daily event loop (lesson 02 §1).

One session, in this order, and the order is the point:

    1. exits     resting brackets resolve against today's bar (gaps first, then the pessimistic
                 ambiguous-bar rule), freeing cash
    2. entries   limit orders placed yesterday fill or expire; market orders fill at the open
    3. mark      equity at the close; estimated tax is paid when the calendar says so
    4. decide    the strategy sees data up to and including today and places orders for tomorrow

Step 4 is last and is handed a `DataView` pinned at `t`, so no strategy can read tomorrow's bar.
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd

from liquid_atm_quant.backtest.broker_sim import Bar, entry_fill, exit_fill, market_fill
from liquid_atm_quant.backtest.costs import CostModel
from liquid_atm_quant.backtest.panel import Panel
from liquid_atm_quant.backtest.portfolio import PendingEntry, PendingMarket, Portfolio, Position
from liquid_atm_quant.backtest.strategy import (BracketIntent, PortfolioSnapshot, Strategy,
                                                TargetWeight)
from liquid_atm_quant.tax.ledger import TaxConfig, TaxLedger
from liquid_atm_quant.tax.lots import ExitReason
from liquid_atm_quant.tax.money import ZERO, cents, money, qty as as_qty

log = logging.getLogger("backtest")


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: Decimal = Decimal("100000.00")

    # Fill realism (lesson 02 §3)
    entry_buffer: Decimal = Decimal("0.01")
    """How far through a limit the bar must trade. Raise it for the strict-fill sensitivity run."""
    strict_fills: bool = False
    """Treat a touch-only entry as unfilled. The lesson 03 §9 sensitivity run: if the edge vanishes
    with this on, it lived in fills that may never have happened."""
    adv_participation: Decimal = Decimal("0.01")
    adv_window: int = 20
    min_order_notional: Decimal = Decimal("100.00")

    # Portfolio construction (Phase 3 owns the real numbers; these keep the engine testable)
    max_positions: int = 10
    default_time_stop_days: int | None = 10
    allow_fractional: bool = False
    delist_after_missing: int = 5
    """Sessions with no bar from the held identity before the position is cashed out at its last
    mark. Halts of a week are rare in large caps; an acquisition is permanent. The last close is
    right for a cash takeover and optimistic for a failure, so this flatters failures slightly;
    Phase 4's survivorship haircut is where that is paid back."""

    # Tax-aware behaviour (lesson 02 §7)
    december_flush: bool = False
    december_flush_month_day: tuple[int, int] = (12, 22)
    """The flush runs on the first session on or after this month/day, leaving 31 days of the
    30-day window inside the old year - which still costs 31 days out of the market."""
    honour_blacklist: bool = True
    apply_dividends: bool = True
    qualified_holding_days: int = 61
    """A distribution counts as qualified only once the position has been held this long. Below it
    the dividend is ordinary income at the full rate - which is what a swing bot mostly collects."""

    tax: TaxConfig = field(default_factory=TaxConfig)
    costs: CostModel = field(default_factory=CostModel)
    risk_free_rate: Decimal = ZERO
    liquidate_at_end: bool = True

    def fingerprint(self) -> str:
        """Stable hash of the whole configuration: Phase 4 counts parameter trials with this."""
        payload = json.dumps(asdict(self), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass
class TradeRecord:
    symbol: str
    entry_date: date
    entry_price: Decimal
    qty: Decimal
    exit_date: date | None = None
    exit_price: Decimal | None = None
    exit_reason: ExitReason | None = None
    fill_kind: str | None = None
    ambiguous_bar: bool = False
    touched_only_entry: bool = False
    days_held: int = 0
    gross_pnl: Decimal = ZERO
    fees: Decimal = ZERO
    realized_gain: Decimal = ZERO          # allowed, after §1091
    disallowed_loss: Decimal = ZERO
    is_long_term: bool = False
    reason: str = ""
    risk_per_share: Decimal | None = None
    """Fill price minus the stop: one R. None for a position without a bracket."""
    r_multiple: float | None = None
    """Exit minus entry, in units of R. Expectancy in R is the first number to read (lesson 03 §5)."""


@dataclass
class BacktestResult:
    strategy: str
    config: BacktestConfig
    config_hash: str
    equity: pd.DataFrame
    """Indexed by session: cash, positions_value, equity, reserve, equity_after_tax, tax_paid_cum."""
    trades: list[TradeRecord]
    ledger: TaxLedger
    diagnostics: dict
    terminal: dict
    strategy_params: dict | None = None

    @property
    def final_equity(self) -> Decimal:
        return cents(self.equity["equity"].iloc[-1])

    @property
    def final_equity_after_tax(self) -> Decimal:
        return cents(self.equity["equity_after_tax"].iloc[-1])

    @property
    def post_liquidation_value(self) -> Decimal:
        """Everything sold and every dollar of tax paid. The only fair cross-strategy number."""
        return cents(self.terminal["post_liquidation_value"])


class Backtester:
    def __init__(self, panel: Panel, config: BacktestConfig | None = None) -> None:
        self.panel = panel
        self.config = config or BacktestConfig()
        self._dividends = self.panel.dividends() if self.config.apply_dividends else {}
        # A session where nothing at all printed is a gap in *our* data (the store is behind the
        # calendar), not news about any one security, so it never counts toward a delisting.
        self._market_printed = np.isfinite(self.panel.column("close")).any(axis=1)

    def run(self, strategy: Strategy, start: date | None = None) -> BacktestResult:
        """`start`: the first session traded. Sessions before it are warm-up history the strategy
        can read (a 200-day average needs 200 days) but that never trade or enter the equity curve.
        """
        cfg = self.config
        t0 = 0 if start is None else next(
            (i for i, s in enumerate(self.panel.sessions) if s >= start), len(self.panel.sessions))
        portfolio = Portfolio(cash=cents(cfg.initial_cash))
        ledger = TaxLedger(cfg.tax)
        pending_entries: list[PendingEntry] = []
        pending_markets: list[PendingMarket] = []
        trades: list[TradeRecord] = []
        open_trades: dict[str, TradeRecord] = {}
        marks: dict[str, Decimal] = {}
        rows: list[dict] = []
        counters = {"entries_filled": 0, "entries_expired": 0, "touch_fills": 0,
                    "exits": 0, "ambiguous_exits": 0, "adv_capped": 0, "cash_capped": 0,
                    "blacklist_blocked": 0, "flush_exits": 0, "dividends": 0,
                    "strict_rejected": 0, "delisted_exits": 0}
        tax_paid = ZERO

        for t, session in enumerate(self.panel.sessions):
            if t < t0:
                continue
            view = self.panel.view(t)

            # ---- 1. exits ----------------------------------------------------------
            for position in list(portfolio.positions.values()):
                bar = self._bar(t, position.symbol)
                if bar is None or self._segment(t, position.symbol) != position.segment:
                    # No print from the company we bought: a halt (the bracket rests) or the end
                    # of the security (acquired, delisted, ticker reused). Only time tells which.
                    position.missing_sessions += bool(self._market_printed[t])
                    if position.missing_sessions >= cfg.delist_after_missing:
                        price = cents(marks.get(position.symbol, position.entry_price))
                        self._sell(portfolio, ledger, position, price, session, "delisted",
                                   trades, open_trades, counters, fill_kind="delisted",
                                   ambiguous=False)
                        counters["delisted_exits"] += 1
                    continue
                position.missing_sessions = 0
                if position.take_profit is None or position.stop_loss is None:
                    continue                    # a baseline holding, exited by rebalance instead
                fill = exit_fill(bar, position.take_profit, position.stop_loss,
                                 position.days_held(t), position.time_stop_days, cfg.costs)
                if fill is None:
                    continue
                self._sell(portfolio, ledger, position, fill.price, session, fill.reason,
                           trades, open_trades, counters, fill_kind=fill.kind,
                           ambiguous=fill.ambiguous)

            # ---- 1b. December flush ------------------------------------------------
            if cfg.december_flush and self._is_flush_session(t):
                for position in list(portfolio.positions.values()):
                    bar = self._bar(t, position.symbol)
                    if bar is None:
                        continue
                    if self._segment(t, position.symbol) != position.segment:
                        continue
                    price = cents(bar.close)
                    if price < position.entry_price:       # harvest losers only
                        self._sell(portfolio, ledger, position, price, session, "december_flush",
                                   trades, open_trades, counters, fill_kind="market",
                                   ambiguous=False)
                        counters["flush_exits"] += 1

            # ---- 2. entries --------------------------------------------------------
            for order in pending_markets:
                bar = self._bar(t, order.symbol)
                if bar is None:
                    continue
                price = market_fill(bar)
                if order.side == "buy":
                    self._buy(portfolio, ledger, order.symbol, order.qty, price, session, t,
                              None, None, None, counters, touched_only=False, reason=order.reason,
                              trades=trades, open_trades=open_trades)
                else:
                    position = portfolio.positions.get(order.symbol)
                    if position is not None and self._segment(t, order.symbol) == position.segment:
                        self._sell(portfolio, ledger, position, price, session, "rebalance", trades,
                                   open_trades, counters, fill_kind="market", ambiguous=False,
                                   partial_qty=min(order.qty, position.qty))
            pending_markets = []

            for order in pending_entries:
                bar = self._bar(t, order.symbol)
                fill = entry_fill(bar, order.limit, cfg.entry_buffer) if bar else None
                if fill is not None and fill.touched_only and cfg.strict_fills:
                    counters["strict_rejected"] += 1
                    fill = None
                if fill is None:
                    counters["entries_expired"] += 1
                    continue
                self._buy(portfolio, ledger, order.symbol, order.qty, fill.price, session, t,
                          order.take_profit, order.stop_loss, order.time_stop_days, counters,
                          touched_only=fill.touched_only, reason=order.reason, trades=trades,
                          open_trades=open_trades)
            pending_entries = []

            # ---- 2b. distributions on anything held through the ex-date ------------
            for position in portfolio.positions.values():
                per_share = self._dividends.get(position.symbol, {}).get(t)
                if per_share is None:
                    continue
                amount = cents(position.qty * money(per_share))
                if amount <= 0:
                    continue
                portfolio.cash += amount
                ledger.dividend(session, amount,
                                qualified=position.days_held(t) >= cfg.qualified_holding_days)
                counters["dividends"] += 1

            # ---- 3. mark and settle ------------------------------------------------
            for symbol, position in portfolio.positions.items():
                close = view.latest("close", symbol)
                if not np.isnan(close) and self._segment(t, symbol) == position.segment:
                    # NOT rounded to cents: a mark is a price, not a cash amount. Rounding here
                    # before multiplying by the share count loses up to half a cent per share,
                    # which is real money on a five-figure position. `positions_value` rounds the
                    # total instead.
                    marks[symbol] = money(close)
            paid = ledger.settle(session)
            if paid > 0:
                portfolio.cash -= paid
                tax_paid += paid
            reserve = ledger.reserve(session)
            equity = portfolio.equity(marks)
            rows.append({"trade_date": session, "cash": portfolio.cash,
                         "positions_value": portfolio.positions_value(marks), "equity": equity,
                         "reserve": reserve, "equity_after_tax": cents(equity - reserve),
                         "tax_paid_cum": tax_paid, "n_positions": len(portfolio.positions)})

            # ---- 4. decide ---------------------------------------------------------
            if t + 1 >= len(self.panel.sessions):
                break
            snapshot = PortfolioSnapshot(
                as_of=session, equity=equity, cash=portfolio.cash,
                sizable_cash=portfolio.sizable_cash(reserve),
                positions={s: p.qty for s, p in portfolio.positions.items()},
                blacklist=frozenset(ledger.blacklist),
                stops={s: p.stop_loss for s, p in portfolio.positions.items()
                       if p.stop_loss is not None})
            orders = strategy.on_close(view, snapshot)
            entries, markets = self._place(orders, view, portfolio, snapshot, ledger, counters)
            pending_entries, pending_markets = entries, markets

        # ---- terminal ---------------------------------------------------------------
        terminal = self._finalize(portfolio, ledger, marks, trades, open_trades, counters,
                                  tax_paid)
        equity_frame = pd.DataFrame(rows).set_index("trade_date")
        diagnostics = self._diagnostics(counters, trades, equity_frame, ledger)
        extra = getattr(strategy, "diagnostics", None)
        if callable(extra):
            diagnostics["strategy"] = extra()
        return BacktestResult(getattr(strategy, "name", type(strategy).__name__), cfg,
                              run_hash(cfg, strategy), equity_frame, trades, ledger, diagnostics,
                              terminal, strategy_params(strategy))

    # ---- order placement -------------------------------------------------------------

    def _place(self, orders, view, portfolio, snapshot, ledger, counters):
        cfg = self.config
        entries: list[PendingEntry] = []
        markets: list[PendingMarket] = []
        budget = snapshot.sizable_cash
        slots = cfg.max_positions - len(portfolio.positions)

        for order in orders:
            if isinstance(order, TargetWeight):
                markets.extend(self._rebalance(order, view, portfolio, snapshot))
                continue
            if not isinstance(order, BracketIntent):
                raise TypeError(f"unexpected order {order!r}")
            if cfg.honour_blacklist and ledger.is_blacklisted(order.symbol, view.today):
                counters["blacklist_blocked"] += 1
                continue
            if order.symbol in portfolio.positions or slots <= 0:
                continue
            quantity = self._size(order, view, snapshot, budget, counters)
            if quantity <= 0:
                continue
            entries.append(PendingEntry(order.symbol, order.entry_limit, quantity,
                                        order.take_profit, order.stop_loss,
                                        order.time_stop_days if order.time_stop_days is not None
                                        else cfg.default_time_stop_days,
                                        order.reason, order.regime))
            budget -= cents(quantity * order.entry_limit)
            slots -= 1
        return entries, markets

    def _size(self, intent: BracketIntent, view, snapshot, budget: Decimal,
              counters: dict) -> Decimal:
        """Fixed-fractional risk sizing, then the two caps that make the fill plausible."""
        cfg = self.config
        if intent.notional is not None:
            notional = intent.notional
        else:
            risk_per_share = intent.entry_limit - intent.stop_loss
            notional = cents(snapshot.equity * intent.risk_fraction
                             / risk_per_share * intent.entry_limit)

        # Cap 1: a share of trailing dollar volume known today, never tomorrow's volume.
        adv_cap = cents(money(view.adv(intent.symbol, cfg.adv_window)) * cfg.adv_participation)
        if adv_cap > 0 and notional > adv_cap:
            notional = adv_cap
            counters["adv_capped"] += 1
        # Cap 2: cash that is not reserved for tax.
        if notional > budget:
            notional = budget
            counters["cash_capped"] += 1
        if notional < cfg.min_order_notional:
            return ZERO

        raw = notional / intent.entry_limit
        return as_qty(raw) if cfg.allow_fractional else as_qty(int(raw))

    def _rebalance(self, order: TargetWeight, view, portfolio, snapshot) -> list[PendingMarket]:
        price = view.latest("close", order.symbol)
        if np.isnan(price) or price <= 0:
            return []
        shares = cents(snapshot.equity * order.weight) / cents(price)
        target_qty = as_qty(shares) if self.config.allow_fractional else as_qty(int(shares))
        current = portfolio.positions.get(order.symbol)
        held = current.qty if current else ZERO
        delta = target_qty - held
        if delta == 0:
            return []
        side = "buy" if delta > 0 else "sell"
        return [PendingMarket(order.symbol, side, abs(delta), order.reason)]

    # ---- fills -----------------------------------------------------------------------

    def _bar(self, t: int, symbol: str) -> Bar | None:
        j = self.panel.index.get(symbol)
        if j is None:
            return None
        o = self.panel.arrays["open"][t, j]
        if np.isnan(o):
            return None
        return Bar(float(o), float(self.panel.arrays["high"][t, j]),
                   float(self.panel.arrays["low"][t, j]), float(self.panel.arrays["close"][t, j]),
                   float(self.panel.arrays["volume"][t, j]))

    def _segment(self, t: int, symbol: str) -> int:
        j = self.panel.index.get(symbol)
        return -1 if j is None else int(self.panel.segment_id[t, j])

    def _buy(self, portfolio, ledger, symbol, quantity, price, session, t, take_profit, stop_loss,
             time_stop_days, counters, touched_only, reason, trades, open_trades) -> None:
        cost = cents(quantity * price)
        fees = self.config.costs.buy_fees(cost, quantity)
        if cost + fees > portfolio.cash:
            # Sized at yesterday's close, filling at today's open: a gap up can make the order
            # unaffordable. Shrink it to what the cash covers rather than dropping it, which would
            # silently leave a buy-and-hold benchmark under-invested for the whole run.
            affordable = portfolio.cash / price
            quantity = as_qty(affordable) if self.config.allow_fractional else as_qty(int(affordable))
            counters["cash_capped"] += 1
            if quantity <= 0:
                return
            cost = cents(quantity * price)
            fees = self.config.costs.buy_fees(cost, quantity)
            if cost + fees > portfolio.cash:
                return
        portfolio.cash -= cost + fees
        ledger.buy(session, symbol, quantity, price, fees)
        existing = portfolio.positions.get(symbol)
        if existing is not None:
            # A tranche on top of an open position: the ledger keeps the lots apart, the position
            # record carries the blended entry for reporting only.
            total = existing.qty + quantity
            existing.entry_price = cents((existing.entry_price * existing.qty + cost) / total)
            existing.qty = total
        else:
            portfolio.positions[symbol] = Position(
                symbol, quantity, price, session, t, take_profit, stop_loss, time_stop_days,
                touched_only, reason, segment=self._segment(t, symbol))
            risk = price - stop_loss if stop_loss is not None and price > stop_loss else None
            open_trades[symbol] = TradeRecord(symbol, session, price, quantity,
                                              touched_only_entry=touched_only, reason=reason,
                                              risk_per_share=risk)
        counters["entries_filled"] += 1
        counters["touch_fills"] += bool(touched_only)

    def _sell(self, portfolio, ledger, position: Position, price: Decimal, session: date,
              reason: ExitReason, trades, open_trades, counters, fill_kind: str, ambiguous: bool,
              partial_qty: Decimal | None = None) -> None:
        quantity = partial_qty if partial_qty is not None else position.qty
        gross = cents(quantity * price)
        fees = self.config.costs.sell_fees(gross, quantity)
        portfolio.cash += gross - fees
        disposals = ledger.sell(session, position.symbol, quantity, price, fees, reason)

        record = open_trades.get(position.symbol)
        if record is not None:
            record.exit_date = session
            record.exit_price = price
            record.exit_reason = reason
            record.fill_kind = fill_kind
            record.ambiguous_bar = ambiguous
            record.days_held = (session - record.entry_date).days
            record.fees = cents(record.fees + fees)
            record.gross_pnl = cents(gross - fees - record.entry_price * quantity)
            record.realized_gain = cents(sum((d.allowed_gain for d in disposals), ZERO))
            record.disallowed_loss = cents(sum((d.disallowed_loss for d in disposals), ZERO))
            record.is_long_term = any(d.is_long_term for d in disposals)
            if record.risk_per_share:
                record.r_multiple = float((price - record.entry_price) / record.risk_per_share)

        position.qty -= quantity
        if position.qty <= 0:
            del portfolio.positions[position.symbol]
            if record is not None:
                trades.append(record)
                del open_trades[position.symbol]
        counters["exits"] += 1
        counters["ambiguous_exits"] += bool(ambiguous)

    # ---- finishing -------------------------------------------------------------------

    def _is_flush_session(self, t: int) -> bool:
        """The first session on or after the configured December date, once per year."""
        month, day = self.config.december_flush_month_day
        session = self.panel.sessions[t]
        if (session.month, session.day) < (month, day) or session.month != month:
            return False
        previous = self.panel.sessions[t - 1] if t else None
        return previous is None or previous < date(session.year, month, day)

    def _finalize(self, portfolio, ledger, marks, trades, open_trades, counters, tax_paid) -> dict:
        """Liquidate at the last close and pay every remaining dollar of tax (lesson 02 §9).

        Without this, a strategy that never sells looks better than one that does, purely because
        its tax bill is invisible. SPY buy-and-hold is exactly that strategy.
        """
        last_session = self.panel.sessions[-1]
        equity_before = portfolio.equity(marks)
        if not self.config.liquidate_at_end:
            return {"post_liquidation_value": cents(equity_before - ledger.reserve(last_session)),
                    "liquidated": False, "tax_paid_cum": tax_paid,
                    "unrealized_at_end": ZERO}

        unrealized = ZERO
        for position in list(portfolio.positions.values()):
            # A fill price *is* a cash amount, so here the mark is quantized.
            price = cents(marks.get(position.symbol, position.entry_price))
            unrealized += cents((price - position.entry_price) * position.qty)
            self._sell(portfolio, ledger, position, price, last_session,
                       "terminal_liquidation", trades, open_trades, counters, fill_kind="market",
                       ambiguous=False)
        final_tax = ledger.reserve(last_session)
        return {"post_liquidation_value": cents(portfolio.cash - final_tax),
                "liquidated": True,
                "cash_after_liquidation": portfolio.cash,
                "terminal_tax": final_tax,
                "tax_paid_cum": tax_paid,
                "unrealized_at_end": cents(unrealized)}

    def _diagnostics(self, counters: dict, trades, equity: pd.DataFrame, ledger) -> dict:
        placed = counters["entries_filled"] + counters["entries_expired"]
        exits = counters["exits"] or 1
        return {
            **counters,
            "n_trades": len(trades),
            "fill_rate": round(counters["entries_filled"] / placed, 4) if placed else 0.0,
            # If this is high the result is mostly an artefact of the stop-wins rule (lesson 02 §2).
            "ambiguity_rate": round(counters["ambiguous_exits"] / exits, 4),
            # If the edge lives in these fills, there is no edge (lesson 02 §3).
            "touch_fill_rate": round(counters["touch_fills"] / counters["entries_filled"], 4)
            if counters["entries_filled"] else 0.0,
            "exposure": round(float((equity["n_positions"] > 0).mean()), 4) if len(equity) else 0.0,
            "dividends_received": ledger.dividends_received,
            "gross_realized_gain": ledger.gross_realized_gain,
            "allowed_realized_gain": ledger.realized_gain,
            "deferred_loss_balance": ledger.deferred_loss_balance,
            "wash_sales": sum(1 for d in ledger.book.disposals if d.disallowed_loss > 0),
            "skipped_prior_sale_matches": len(ledger.matcher.skipped_prior_sale),
        }


def strategy_params(strategy: Strategy) -> dict | None:
    params = getattr(strategy, "params", None)
    return asdict(params) if params is not None and hasattr(params, "__dataclass_fields__")         else None


def run_hash(config: BacktestConfig, strategy: Strategy) -> str:
    """One trial = one engine configuration *and* one strategy parameter set (lesson 03 §1).

    A strategy without parameters keeps the bare engine fingerprint, so the Phase 2 baseline
    hashes already stored in `backtest_runs` stay valid.
    """
    params = strategy_params(strategy)
    if params is None:
        return config.fingerprint()
    payload = json.dumps({"engine": config.fingerprint(), "strategy": params}, sort_keys=True,
                         default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def run_backtest(panel: Panel, strategy: Strategy, config: BacktestConfig | None = None,
                 start: date | None = None) -> BacktestResult:
    return Backtester(panel, config).run(strategy, start)


__all__ = ["BacktestConfig", "BacktestResult", "Backtester", "TradeRecord", "run_backtest",
           "run_hash"]
