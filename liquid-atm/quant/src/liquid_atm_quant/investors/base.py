"""Turning a target portfolio into orders, the same way for every Phase 3b strategy (lesson 03b §3).

Each investor strategy answers one question - "what should I own, and how much?" - by returning a
`{symbol: weight}` dict (or None for "no change today"). `PortfolioStrategy` does the rest, with
four rules that matter more for after-tax money than any stock-picking detail:

1. **Sells before buys.** The engine fills market orders at the open in the order given, so the
   cash from a sale has to arrive before the purchase that needs it.
2. **The tax reserve is not investable.** Weights are scaled by (equity - reserve) / equity, so a
   strategy never spends money owed to the IRS (lesson 02 §7).
3. **A no-trade band.** A holding still wanted is only resized when it is more than `band` away
   (relative) from its target. Trimming a winner every month realizes short-term gains at 32%;
   letting it drift until it matters can let the gain age past a year and be taxed at 15%.
4. **Selections are remembered by the strategy, not read back from the book**, so the same
   strategy can run as one sleeve of a combination without mistaking the other sleeve's holdings
   for its own.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import numpy as np

from liquid_atm_quant.backtest.panel import DataView
from liquid_atm_quant.backtest.strategy import PortfolioSnapshot, TargetWeight

GROSS = 0.98
"""Fraction of investable equity put to work: the rest absorbs costs and next-open gaps, so
rebalance buys are not cash-capped."""

NO_RESIZE = float("inf")


def first_session_of_month(today: date, last: date | None) -> bool:
    return last is None or (today.year, today.month) != (last.year, last.month)


def first_session_of_quarter(today: date, last: date | None) -> bool:
    return last is None or (today.year, (today.month - 1) // 3) != (last.year,
                                                                   (last.month - 1) // 3)


@dataclass
class TargetBook:
    """The portfolio-to-orders adapter: strategies own one and pass it their targets."""

    band: float = 0.5
    overrides: dict[str, float] | None = None
    """Per-symbol bands, e.g. a trend book that never resizes positions but does top up cash."""

    def orders(self, targets: dict[str, float], view: DataView,
               book: PortfolioSnapshot) -> list[TargetWeight]:
        equity = float(book.equity)
        if equity <= 0:
            return []
        reserve = max(0.0, float(book.cash - book.sizable_cash))
        scale = GROSS * (equity - reserve) / equity

        current: dict[str, float] = {}
        for symbol, qty in book.positions.items():
            price = view.latest("close", symbol)
            current[symbol] = float(qty) * float(price) / equity if np.isfinite(price) else np.nan

        sells: list[TargetWeight] = []
        buys: list[TargetWeight] = []
        for symbol, weight in current.items():
            if targets.get(symbol, 0.0) <= 0:
                sells.append(TargetWeight(symbol, Decimal(0), reason="exit"))
        for symbol, raw in targets.items():
            if raw <= 0:
                continue
            target = raw * scale
            have = current.get(symbol)
            if have is None:
                buys.append(TargetWeight(symbol, _w(target), reason="enter"))
            elif np.isfinite(have) and abs(have - target) > self._band(symbol) * target:
                order = TargetWeight(symbol, _w(target), reason="resize")
                (buys if target > have else sells).append(order)
        return sells + buys


    def _band(self, symbol: str) -> float:
        return (self.overrides or {}).get(symbol, self.band)


def _w(weight: float) -> Decimal:
    return Decimal(str(round(weight, 6)))


class PortfolioStrategy:
    """Base for target-portfolio strategies: subclasses implement `targets()`."""

    name = "portfolio"
    band = 0.5
    band_overrides: dict[str, float] | None = None

    def __init__(self) -> None:
        self._book = TargetBook(self.band, self.band_overrides)
        self._decisions = 0

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        raise NotImplementedError

    def on_close(self, view: DataView, book: PortfolioSnapshot) -> list:
        wanted = self.targets(view, book)
        if wanted is None:
            return []
        self._decisions += 1
        return self._book.orders(wanted, view, book)


def equal_weight(symbols: list[str]) -> dict[str, float]:
    return {s: 1.0 / len(symbols) for s in symbols} if symbols else {}


__all__ = ["GROSS", "NO_RESIZE", "PortfolioStrategy", "TargetBook", "equal_weight",
           "first_session_of_month", "first_session_of_quarter"]
