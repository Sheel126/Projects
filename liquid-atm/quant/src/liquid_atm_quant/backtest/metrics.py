"""Performance metrics (lesson 02 §10).

Every metric is computed on whichever equity column it is handed, so the same code produces the
pre-tax and the after-tax view. Two conventions worth knowing before reading a number out of here:

* **Calmar is the headline**, not Sharpe. The Phase 4 gate is drawdown-constrained, and Sharpe does
  not care whether the volatility arrived as a grind or as one 30% hole.
* **The risk-free rate is explicit and shared.** It defaults to zero, it is recorded in the output,
  and the baselines are measured with the same value as the strategy. T-bills paid ~0% in 2021 and
  ~5% in 2024, so a Sharpe quoted without its rate means nothing.

Deflated Sharpe and PBO belong to Phase 4; they need the number of parameter trials, which is why
`config_hash` travels with every run.
"""

from dataclasses import asdict, dataclass
from decimal import Decimal

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass(frozen=True)
class Metrics:
    start: object
    end: object
    years: float
    initial: float
    final: float
    total_return: float
    cagr: float
    volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    max_drawdown_start: object
    max_drawdown_end: object
    calmar: float
    best_day: float
    worst_day: float
    risk_free_rate: float

    def as_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        return (f"CAGR {self.cagr:7.2%}   vol {self.volatility:6.2%}   Sharpe {self.sharpe:5.2f}   "
                f"maxDD {self.max_drawdown:7.2%}   Calmar {self.calmar:5.2f}")


def drawdown(equity: pd.Series) -> pd.Series:
    peak = equity.cummax()
    return equity / peak - 1.0


def compute(equity: pd.Series, risk_free_rate: float = 0.0) -> Metrics:
    """`equity` is a date-indexed series of account value; one point per trading session."""
    series = pd.Series(equity).astype(float).dropna()
    if len(series) < 2:
        raise ValueError("need at least two equity points")

    returns = series.pct_change().dropna()
    years = len(series) / TRADING_DAYS
    total = series.iloc[-1] / series.iloc[0] - 1.0
    cagr = (series.iloc[-1] / series.iloc[0]) ** (1 / years) - 1.0 if years > 0 else 0.0

    volatility = float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS))
    daily_rf = (1 + risk_free_rate) ** (1 / TRADING_DAYS) - 1
    excess = returns - daily_rf
    sharpe = float(excess.mean() / returns.std(ddof=1) * np.sqrt(TRADING_DAYS)) \
        if returns.std(ddof=1) > 0 else 0.0
    # Sortino penalises only downside deviation, which is the asymmetry a stop-based strategy has.
    # With no downside at all the ratio is undefined, and it is reported as NaN rather than as
    # infinity on purpose: an infinity silently wins any `max()` ranking, which is exactly how
    # Phase 4's parameter search would talk itself into a curve with too little history.
    downside = excess.clip(upper=0)
    downside_dev = float(np.sqrt((downside ** 2).mean()) * np.sqrt(TRADING_DAYS))
    sortino = float(excess.mean() * TRADING_DAYS / downside_dev) if downside_dev > 0 \
        else float("nan")

    dd = drawdown(series)
    max_dd = float(dd.min())
    trough = dd.idxmin()
    peak = series.loc[:trough].idxmax()
    # Calmar with a floor on the denominator: a strategy with no drawdown yet is not infinitely good.
    calmar = float(cagr / abs(max_dd)) if max_dd < -1e-9 else float("nan")

    return Metrics(
        start=series.index[0], end=series.index[-1], years=round(years, 3),
        initial=float(series.iloc[0]), final=float(series.iloc[-1]), total_return=float(total),
        cagr=float(cagr), volatility=volatility, sharpe=sharpe, sortino=sortino,
        max_drawdown=max_dd, max_drawdown_start=peak, max_drawdown_end=trough, calmar=calmar,
        best_day=float(returns.max()), worst_day=float(returns.min()),
        risk_free_rate=float(risk_free_rate))


@dataclass(frozen=True)
class TradeStats:
    n_trades: int
    hit_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    payoff_ratio: float
    avg_days_held: float
    exit_reasons: dict
    ambiguous_share: float
    touch_entry_share: float
    wash_sale_trades: int
    long_term_trades: int
    expectancy_r: float = float("nan")
    """Mean exit-minus-entry in units of initial risk, over bracketed trades only. Gross of tax.
    Lesson 03 §5: a bracket with no drift is worth exactly 0 R, so this is the screener's score."""
    avg_win_r: float = float("nan")
    avg_loss_r: float = float("nan")

    def as_dict(self) -> dict:
        return asdict(self)


def trade_stats(trades: list) -> TradeStats:
    """`trades` is the engine's list of `TradeRecord`. Closed trades only."""
    closed = [t for t in trades if t.exit_date is not None]
    if not closed:
        return TradeStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, {}, 0.0, 0.0, 0, 0)
    pnl = [float(t.gross_pnl) for t in closed]
    wins = [x for x in pnl if x > 0]
    losses = [x for x in pnl if x < 0]
    gross_win, gross_loss = sum(wins), -sum(losses)
    r = [t.r_multiple for t in closed if getattr(t, "r_multiple", None) is not None]
    win_r, loss_r = [x for x in r if x > 0], [x for x in r if x <= 0]
    reasons: dict[str, int] = {}
    for t in closed:
        reasons[str(t.exit_reason)] = reasons.get(str(t.exit_reason), 0) + 1
    return TradeStats(
        n_trades=len(closed),
        hit_rate=len(wins) / len(closed),
        avg_win=gross_win / len(wins) if wins else 0.0,
        avg_loss=-gross_loss / len(losses) if losses else 0.0,
        profit_factor=gross_win / gross_loss if gross_loss > 0 else float("inf"),
        payoff_ratio=((gross_win / len(wins)) / (gross_loss / len(losses)))
        if wins and losses else float("nan"),
        avg_days_held=sum(t.days_held for t in closed) / len(closed),
        exit_reasons=dict(sorted(reasons.items())),
        ambiguous_share=sum(t.ambiguous_bar for t in closed) / len(closed),
        touch_entry_share=sum(t.touched_only_entry for t in closed) / len(closed),
        wash_sale_trades=sum(1 for t in closed if t.disallowed_loss > 0),
        long_term_trades=sum(1 for t in closed if t.is_long_term),
        expectancy_r=sum(r) / len(r) if r else float("nan"),
        avg_win_r=sum(win_r) / len(win_r) if win_r else float("nan"),
        avg_loss_r=sum(loss_r) / len(loss_r) if loss_r else float("nan"))


@dataclass(frozen=True)
class TaxSummary:
    gross_realized: float
    allowed_realized: float
    deferred_loss_balance: float
    tax_paid: float
    terminal_tax: float
    effective_tax_rate: float
    """Total tax divided by total economic profit. Above the statutory rate means wash sales or
    year-boundary netting deferred deductions into a future year."""

    def as_dict(self) -> dict:
        return asdict(self)


def tax_summary(result) -> TaxSummary:
    terminal = result.terminal
    paid = float(terminal.get("tax_paid_cum", 0) or 0)
    terminal_tax = float(terminal.get("terminal_tax", 0) or 0)
    total_tax = paid + terminal_tax
    profit = float(result.post_liquidation_value) + total_tax - float(result.config.initial_cash)
    return TaxSummary(
        gross_realized=float(result.ledger.gross_realized_gain),
        allowed_realized=float(result.ledger.realized_gain),
        deferred_loss_balance=float(result.ledger.deferred_loss_balance),
        tax_paid=paid, terminal_tax=terminal_tax,
        effective_tax_rate=total_tax / profit if profit > 1e-9 else 0.0)


def report(result) -> dict:
    """Everything Phase 4 needs from one run, as plain JSON-able values."""
    rf = float(result.config.risk_free_rate)
    pre = compute(result.equity["equity"], rf)
    post = compute(result.equity["equity_after_tax"], rf)
    return {
        "strategy": result.strategy,
        "config_hash": result.config_hash,
        "pre_tax": pre.as_dict(),
        "after_tax": post.as_dict(),
        "post_liquidation_value": float(result.post_liquidation_value),
        "trades": trade_stats(result.trades).as_dict(),
        "tax": tax_summary(result).as_dict(),
        "diagnostics": {k: (float(v) if isinstance(v, Decimal) else v)
                        for k, v in result.diagnostics.items()},
    }
