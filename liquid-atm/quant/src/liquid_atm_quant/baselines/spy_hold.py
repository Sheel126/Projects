"""Buy and hold one ETF, forever (lesson 02 §9).

This is the benchmark that actually matters: it is what the money would do if the bot did not exist.
Two things make it a harder benchmark than it looks.

1. **Its gains are never realized**, so no tax is paid year to year. The running after-tax curve
   therefore flatters it, and the fair comparison is the engine's post-liquidation value, where
   everything is sold and the deferred bill finally comes due at the long-term rate.
2. **Its dividends are taxed every year** at the qualified rate, which is a real drag the bot does
   not pay on positions it flips before any ex-date. Those dividends are recovered from the
   `adj_factor` path by `Panel.dividends()` rather than from a dividend feed we do not have, and
   the engine credits them as cash and taxes them.

It is also the engine's self-test: run SPY through it and the result must reproduce SPY's published
CAGR and max drawdown for the window. If it does not, nothing downstream means anything.
"""

from dataclasses import dataclass
from decimal import Decimal

import numpy as np

from liquid_atm_quant.backtest.panel import DataView
from liquid_atm_quant.backtest.strategy import PortfolioSnapshot, TargetWeight


@dataclass
class BuyAndHold:
    """Deploy `weight` of the account into `symbol` on the first session it trades, then sit."""

    symbol: str = "SPY"
    weight: Decimal = Decimal("1.0")
    reinvest: bool = True
    """Put distributions back into the position as soon as they cover a share.

    This matters more than it looks. Left as idle cash, ten years of SPY distributions are well
    over a tenth of the account sitting uninvested, which drags the benchmark's CAGR down and
    cushions its drawdowns - i.e. it makes the benchmark easier to beat. A real buy-and-hold
    investor reinvests, and the published total-return figures this baseline is checked against
    assume reinvestment, so the default is on.
    """
    name: str = "buy_and_hold"

    def __post_init__(self) -> None:
        self.name = f"buy_and_hold_{self.symbol.lower()}"
        self._placed = False

    def on_close(self, view: DataView, book: PortfolioSnapshot) -> list:
        price = view.latest("close", self.symbol)
        if np.isnan(price):
            return []
        if not self._placed and not book.holds(self.symbol):
            self._placed = True
            return [TargetWeight(self.symbol, self.weight, reason="buy_and_hold")]
        # Topping the weight back up only ever buys: the target is equity * weight, and cash only
        # accumulates from distributions, so this never sells and never churns.
        if self.reinvest and book.sizable_cash >= Decimal(repr(float(price))):
            return [TargetWeight(self.symbol, self.weight, reason="reinvest_distribution")]
        return []
