"""Naive cross-sectional momentum: the screen anyone could run in an afternoon (lesson 02 §9).

Top decile by 12-month total return, rebalanced monthly, equal weight, no regime filter, no
catalyst check, no brackets. Every gain is short term, so it pays the full tax rate.

This is the baseline that tells you whether the Phase 3 funnel is an edge or a decoration. If the
regime filter, the ATR brackets and the LLM veto cannot beat this, they are not earning their
complexity.

Two rules it inherits from Phase 1 rather than inventing:

* Returns are computed on **adjusted** prices (`raw * adj_factor`) - price levels would make the
  2020 Apple split look like a 74% crash.
* The lookback must stay inside **one identity segment**, so a ranking window never spans two
  companies that shared a ticker.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import numpy as np

from liquid_atm_quant.backtest.panel import DataView
from liquid_atm_quant.backtest.strategy import PortfolioSnapshot, TargetWeight

LOOKBACK = 252          # about 12 months of sessions
SKIP = 21               # skip the most recent month: classic 12-1 momentum


@dataclass
class NaiveMomentum:
    lookback: int = LOOKBACK
    skip: int = SKIP
    top_n: int = 10
    min_price: Decimal = Decimal("10.00")
    min_dollar_volume: float = 5_000_000.0
    name: str = "naive_momentum"
    _last_rebalance: date | None = field(default=None, repr=False)

    def on_close(self, view: DataView, book: PortfolioSnapshot) -> list:
        if not self._is_rebalance(view.today):
            return []
        self._last_rebalance = view.today

        ranked = self._rank(view)
        if not ranked:
            return []
        chosen = [symbol for symbol, _ in ranked[:self.top_n]]
        weight = Decimal(1) / Decimal(len(chosen))

        orders = [TargetWeight(symbol, weight, reason="momentum_top_decile") for symbol in chosen]
        # Exit anything that dropped out of the ranking. The engine turns a zero weight into a sell.
        orders += [TargetWeight(symbol, Decimal(0), reason="momentum_drop")
                   for symbol in book.positions if symbol not in chosen]
        return orders

    def _is_rebalance(self, today: date) -> bool:
        """First session of each calendar month."""
        return self._last_rebalance is None or (today.year, today.month) != (
            self._last_rebalance.year, self._last_rebalance.month)

    def _rank(self, view: DataView) -> list[tuple[str, float]]:
        window = self.lookback + self.skip
        out: list[tuple[str, float]] = []
        for symbol in view.universe():
            # Price and liquidity floors use RAW prices and real dollar volume (lesson 01 §2).
            price = view.latest("close", symbol)
            if not np.isfinite(price) or price < float(self.min_price):
                continue
            if view.adv(symbol, 20) < self.min_dollar_volume:
                continue
            if not view.same_segment(symbol, window):
                continue
            closes = view.history("close", symbol, window, adjusted=True)
            if len(closes) < window or not np.isfinite(closes[0]):
                continue
            start, end = closes[0], closes[-1 - self.skip]
            if not np.isfinite(end) or start <= 0:
                continue
            out.append((symbol, float(end / start - 1.0)))
        out.sort(key=lambda row: row[1], reverse=True)
        return out
