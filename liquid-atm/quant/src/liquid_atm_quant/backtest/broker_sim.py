"""Fill simulation for daily bars (lesson 02 §2-§3).

Pure functions on one bar, so the two rules that decide whether a backtest is honest are testable
in isolation:

* **Exits** resolve gaps first, then treat a bar that touched both the stop and the target as a
  stop. That is pessimistic on purpose: the alternative is a free parameter for Phase 4 to overfit.
* **Entries** fill a limit at `min(open, limit)`, optionally requiring the bar to trade *through*
  the limit rather than merely touch it.

Market data is `float` (it comes from the numpy panel); money becomes `Decimal` at the moment a
fill exists, and never goes back. That boundary is here.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from liquid_atm_quant.backtest.costs import CostModel
from liquid_atm_quant.tax.lots import ExitReason
from liquid_atm_quant.tax.money import cents

FillKind = Literal["gap_stop", "gap_target", "ambiguous_stop", "stop", "target", "time_stop",
                   "market", "delisted"]


@dataclass(frozen=True)
class Bar:
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def contains(self, price: float) -> bool:
        return self.low <= price <= self.high


@dataclass(frozen=True)
class EntryFill:
    price: Decimal
    touched_only: bool
    """True when the bar reached the limit but never traded meaningfully through it. These fills
    are where a daily-bar backtest is most likely to be lying (lesson 02 §3)."""


@dataclass(frozen=True)
class ExitFill:
    price: Decimal
    reason: ExitReason
    kind: FillKind
    ambiguous: bool
    """The bar touched both the stop and the target, so the order was unknowable."""


def entry_fill(bar: Bar, limit: Decimal, buffer: Decimal = Decimal("0.01")) -> EntryFill | None:
    """A resting buy limit against one bar.

    `buffer` is how far *through* the limit the bar must trade for the fill to count. The default
    of one cent means a bar whose low exactly equals the limit still fills but is flagged; raise
    the buffer for the strict mode Phase 4 uses to test how much of the edge lives in those fills.
    """
    limit_f = float(limit)
    if bar.open <= limit_f:
        # Gapped below the limit: the open is the first tradable price and it is better than asked.
        return EntryFill(cents(bar.open), touched_only=False)
    if bar.low > limit_f:
        return None
    through = bar.low <= limit_f - float(buffer)
    return EntryFill(cents(limit), touched_only=not through)


def exit_fill(bar: Bar, take_profit: Decimal, stop_loss: Decimal, days_held: int,
              time_stop_days: int | None, costs: CostModel) -> ExitFill | None:
    """Resolve a resting bracket against one bar, in the fixed order from lesson 02 §2."""
    target, stop = float(take_profit), float(stop_loss)

    # 1-2. Gaps. The open is the first price that traded, so it is the fill, and no extra slippage
    # is charged on top: the gap already is the slippage.
    if bar.open <= stop:
        return ExitFill(cents(bar.open), "stop_loss", "gap_stop", ambiguous=False)
    if bar.open >= target:
        return ExitFill(cents(bar.open), "take_profit", "gap_target", ambiguous=False)

    hit_stop, hit_target = bar.low <= stop, bar.high >= target

    # 3. Both touched inside one bar: unknowable order, so the stop wins.
    if hit_stop and hit_target:
        return ExitFill(_stop_price(stop_loss, costs), "stop_loss", "ambiguous_stop", ambiguous=True)
    if hit_stop:
        return ExitFill(_stop_price(stop_loss, costs), "stop_loss", "stop", ambiguous=False)
    if hit_target:
        # A take profit is a limit order: it fills at the limit, never worse.
        return ExitFill(cents(take_profit), "take_profit", "target", ambiguous=False)

    # 6. Nothing triggered. The time stop exits at the close.
    if time_stop_days is not None and days_held >= time_stop_days:
        return ExitFill(cents(bar.close), "time_stop", "time_stop", ambiguous=False)
    return None


def _stop_price(stop_loss: Decimal, costs: CostModel) -> Decimal:
    """A triggered stop is a market order, so it fills below the stop."""
    return cents(stop_loss - costs.stop_slippage(stop_loss))


def market_fill(bar: Bar) -> Decimal:
    """Market-on-open, used by the rebalancing baselines rather than by the bracket strategy."""
    return cents(bar.open)
