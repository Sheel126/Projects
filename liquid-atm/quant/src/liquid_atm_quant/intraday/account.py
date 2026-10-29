"""After-tax accounting for intraday strategies (lesson 03d §3).

The daily engine cannot run these: it fills at the open and marks at the close, and an intraday
strategy is flat at both. What it needs instead is small:

* each session's net P&L, realized the same day, so **every dollar is short-term** (32%);
* the same `TaxAccount` the engine uses, so netting, carryforwards and the quarterly 1040-ES
  payments are identical;
* optionally a **buy-and-hold SPY core** held in the same account, so "SPY plus an intraday
  overlay" can be measured as one book: one equity curve, one tax return.

Wash sales. A day trade that loses and is followed by another purchase of SPY within 30 days is a
wash sale; the loss moves into the new shares, which are sold the same day, so it is recognized
then. Inside a year the net is unchanged, which is why this module books net daily P&L directly.
What it does not model is the chain crossing 31 December, which can push the last loss of a year
into the next one - a timing cost of one year on at most a few days' losses. The core never buys
again after day one except to reinvest distributions, and the overlay's shares must be sold by
**specific lot** (Phase 6), never FIFO out of the core.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import pandas as pd

from liquid_atm_quant.backtest.costs import CostModel
from liquid_atm_quant.backtest.metrics import compute
from liquid_atm_quant.tax.money import ZERO, cents, money
from liquid_atm_quant.tax.reserve import TaxAccount, TaxRates

QUALIFIED_HOLDING_DAYS = 61
LONG_TERM_DAYS = 365
MARGIN_RATE = 0.08
"""Charged on any negative overnight cash. With a fully invested core, an overlay that loses (or
a tax payment) is paid for with a margin loan, and Alpaca charges for those. 8% a year is above
what Alpaca charged over 2016-2024, positive cash earns nothing, and the interest is not deducted
from tax: all three err against the strategy."""


@dataclass(frozen=True)
class DailyBar:
    """SPY's daily open, close and the distribution going ex today (0.0 if none)."""

    open: float
    close: float
    dividend: float = 0.0


@dataclass
class DayOutcome:
    pnl: float
    """Net of commissions and slippage, in dollars."""
    trades: int = 0
    max_gross: float = 0.0
    """Largest notional held at any moment, as a multiple of the day's sizing capital."""


DayFn = Callable[[date, float], DayOutcome]
"""(session, capital available to size with) -> what the strategy did that day."""


@dataclass
class IntradayResult:
    name: str
    equity: pd.DataFrame
    """Indexed by session: equity, reserve, equity_after_tax, tax_paid_cum, overlay_pnl."""
    post_liquidation_value: float
    trades: int
    days_traded: int
    params: dict = field(default_factory=dict)
    diagnostics: dict = field(default_factory=dict)

    def report(self) -> dict:
        after = compute(self.equity["equity_after_tax"])
        pre = compute(self.equity["equity"])
        initial = float(self.equity["equity"].iloc[0] - self.equity["overlay_pnl"].iloc[0])
        years = after.years
        value = self.post_liquidation_value
        pnl = self.equity["overlay_pnl"]
        return {
            "strategy": self.name,
            "post_liquidation_value": value,
            "after_tax": after.as_dict(),
            "pre_tax": pre.as_dict(),
            "after_tax_cagr_post_liquidation": (value / initial) ** (1 / years) - 1,
            "trades": {"n_trades": self.trades, "days_traded": self.days_traded,
                       "day_hit_rate": float((pnl[pnl != 0] > 0).mean()) if (pnl != 0).any()
                       else 0.0},
            "tax": {"tax_paid": float(self.equity["tax_paid_cum"].iloc[-1]),
                    "terminal_tax": self.diagnostics.get("terminal_tax", 0.0)},
            "params": self.params,
            "diagnostics": self.diagnostics,
        }


def run_account(sessions: list[date], daily: dict[date, DailyBar], day_fn: DayFn | None,
                name: str, initial_cash: float = 100_000.0, core: bool = False,
                overlay_capital: float = 1.0, rates: TaxRates | None = None,
                costs: CostModel | None = None, params: dict | None = None,
                margin_rate: float = MARGIN_RATE) -> IntradayResult:
    """Walk the sessions: intraday P&L, the optional SPY core, distributions, tax, liquidation.

    `overlay_capital` scales the capital the strategy sizes from (after-tax equity at the prior
    close). With a core, leverage caps belong in the strategy, which sees this capital.
    """
    costs = costs or CostModel()
    tax = TaxAccount(rates or TaxRates(), "quarterly")
    cash = money(initial_cash)
    lots: list[tuple[date, int, Decimal]] = []      # core: (bought, shares, price)
    rows = []
    tax_paid = ZERO
    trades = days_traded = 0
    overlay_total = 0.0
    interest_total = ZERO
    prev_after_tax = float(initial_cash)

    for day in sessions:
        bar = daily.get(day)
        if core and not lots and bar is not None:
            price = money(bar.open)
            shares = int(cash / price)
            lots.append((day, shares, price))
            cash -= cents(shares * price)

        # ---- intraday: sized from yesterday's after-tax equity --------------------------
        outcome = day_fn(day, prev_after_tax * overlay_capital) if day_fn is not None else None
        pnl = cents(outcome.pnl) if outcome is not None else ZERO
        if outcome is not None and outcome.trades:
            trades += outcome.trades
            days_traded += 1
        if pnl != 0:
            cash += pnl
            tax.realize(day, pnl, long_term=False)
            overlay_total += float(pnl)

        # ---- distributions on the core, reinvested like the engine's baseline ----------
        held = sum(q for _, q, _ in lots)
        if bar is not None and bar.dividend > 0 and held:
            amount = cents(held * money(bar.dividend))
            cash += amount
            qualified = (day - lots[0][0]).days >= QUALIFIED_HOLDING_DAYS
            tax.dividend(day, amount, qualified=qualified)

        if cash < 0:                             # an overnight margin loan
            interest = cents(-cash * money(margin_rate) / 252)
            cash -= interest
            interest_total += interest

        paid = tax.settle(day)
        cash -= paid
        tax_paid += paid
        reserve = tax.reserve(day)
        if core and bar is not None and lots and cash - reserve >= money(bar.close):
            extra = int((cash - reserve) / money(bar.close))
            if extra > 0:
                lots.append((day, extra, money(bar.close)))
                cash -= cents(extra * money(bar.close))

        close = bar.close if bar is not None else (rows[-1]["close"] if rows else 0.0)
        held = sum(q for _, q, _ in lots)
        equity = float(cash) + held * close
        rows.append({"trade_date": day, "close": close, "equity": equity,
                     "reserve": float(reserve), "equity_after_tax": equity - float(reserve),
                     "tax_paid_cum": float(tax_paid), "overlay_pnl": float(pnl)})
        prev_after_tax = equity - float(reserve)

    # ---- terminal liquidation: sell the core, pay every remaining dollar ---------------
    last = sessions[-1]
    terminal_tax = 0.0
    if lots:
        price = money(rows[-1]["close"])
        shares = sum(q for _, q, _ in lots)
        proceeds = cents(shares * price)
        fees = costs.sell_fees(proceeds, shares)
        cash += proceeds - fees
        for bought, qty, cost in lots:
            share = Decimal(qty) / Decimal(shares)
            gain = cents(qty * (price - cost) - fees * share)
            tax.realize(last, gain, long_term=(last - bought).days > LONG_TERM_DAYS)
    final_reserve = tax.reserve(last)
    terminal_tax = float(final_reserve)
    value = float(cash - final_reserve)

    frame = pd.DataFrame(rows).set_index("trade_date")
    diagnostics = {"terminal_tax": terminal_tax, "overlay_pnl_total": overlay_total,
                   "margin_interest": float(interest_total),
                   "core_shares": sum(q for _, q, _ in lots),
                   "years": {y: {"short_term_net": float(r.short_term_net), "tax": float(r.tax)}
                             for y, r in tax.years(last).items()}}
    return IntradayResult(name, frame, value, trades, days_traded, params or {}, diagnostics)


def calendar_returns(equity: pd.Series) -> dict[int, float]:
    """Calendar-year returns of an equity series (first year from its first point)."""
    series = equity.astype(float)
    out = {}
    years = pd.Index([d.year for d in series.index])
    start = float(series.iloc[0])
    for year in sorted(set(years)):
        end = float(series[years == year].iloc[-1])
        out[year] = end / start - 1
        start = end
    return out


__all__ = ["DailyBar", "DayFn", "DayOutcome", "IntradayResult", "calendar_returns",
           "run_account"]

