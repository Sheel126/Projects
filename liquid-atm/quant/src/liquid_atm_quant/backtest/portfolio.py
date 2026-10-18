"""Cash, open positions and their resting bracket levels.

The tax ledger owns cost basis; this class deliberately does not duplicate it. `entry_price` here
is for reporting a trade's P&L, never for tax: after a wash-sale adjustment the two differ, and the
ledger is the one that is right.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from liquid_atm_quant.tax.money import ZERO, cents


@dataclass
class Position:
    symbol: str
    qty: Decimal
    entry_price: Decimal
    entry_date: date
    entry_session: int
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None
    time_stop_days: int | None = None
    touched_only_entry: bool = False
    reason: str = ""
    segment: int = -1
    """The corporate identity bought (lesson 01 §5b). A bar from any other segment under the same
    ticker belongs to a different company and must never mark or exit this position."""
    missing_sessions: int = 0
    """Consecutive sessions with no bar from `segment`. Enough of them means the security is gone."""

    def days_held(self, session: int) -> int:
        return session - self.entry_session


@dataclass
class PendingEntry:
    """A limit order resting for the next session. `day` time-in-force: one session, then gone."""

    symbol: str
    limit: Decimal
    qty: Decimal
    take_profit: Decimal
    stop_loss: Decimal
    time_stop_days: int | None
    reason: str
    regime: str = ""


@dataclass
class PendingMarket:
    """Market-on-open, used by the rebalancing baselines."""

    symbol: str
    side: str            # 'buy' or 'sell'
    qty: Decimal
    reason: str = ""


@dataclass
class Portfolio:
    cash: Decimal
    positions: dict[str, Position] = field(default_factory=dict)

    def positions_value(self, marks: dict[str, Decimal]) -> Decimal:
        """Marked at the close. A symbol that did not trade today keeps its last known mark."""
        return cents(sum((p.qty * marks[p.symbol] for p in self.positions.values()
                          if p.symbol in marks), ZERO))

    def equity(self, marks: dict[str, Decimal]) -> Decimal:
        return cents(self.cash + self.positions_value(marks))

    def sizable_cash(self, reserve: Decimal) -> Decimal:
        """Cash the strategy may deploy: the tax reserve is held back (lesson 02 §7)."""
        return max(ZERO, cents(self.cash - reserve))
