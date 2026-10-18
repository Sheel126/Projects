"""What a strategy hands the engine, and the protocol it implements.

Two order shapes, because Phase 2 has to carry both the real design and its benchmarks:

* `BracketIntent` — the Phase 3 funnel's output: a limit entry with an ATR-sized take profit,
  stop loss and time stop. It maps one-to-one onto `trade_intents` in the schema and onto an
  Alpaca bracket order in Phase 6.
* `TargetWeight` — a plain market-on-open rebalance, which is all the baselines need. Keeping it
  separate stops the baselines from being expressed as brackets with absurd levels, which would
  make the intrabar rules untestable.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol, runtime_checkable

from liquid_atm_quant.backtest.panel import DataView
from liquid_atm_quant.tax.money import money


@dataclass(frozen=True)
class BracketIntent:
    symbol: str
    entry_limit: Decimal
    take_profit: Decimal
    stop_loss: Decimal
    risk_fraction: Decimal = Decimal("0.01")
    """Fraction of equity risked between the entry and the stop. Sizing is fixed-fractional:
    `qty = risk_fraction * equity / (entry_limit - stop_loss)`."""
    reason: str = ""
    regime: str = ""
    time_stop_days: int | None = None
    notional: Decimal | None = None
    """Overrides fixed-fractional sizing. Used by tests and by any strategy sizing another way."""

    def __post_init__(self) -> None:
        if not (self.stop_loss < self.entry_limit < self.take_profit):
            raise ValueError(f"{self.symbol}: need stop < entry < target, got "
                             f"{self.stop_loss} / {self.entry_limit} / {self.take_profit}")

    @staticmethod
    def of(symbol: str, entry_limit: object, take_profit: object, stop_loss: object,
           risk_fraction: object = "0.01", reason: str = "", regime: str = "",
           time_stop_days: int | None = None, notional: object | None = None) -> "BracketIntent":
        return BracketIntent(symbol, money(entry_limit), money(take_profit), money(stop_loss),
                             money(risk_fraction), reason, regime, time_stop_days,
                             None if notional is None else money(notional))


@dataclass(frozen=True)
class TargetWeight:
    """Rebalance `symbol` to this fraction of equity at tomorrow's open. Zero exits the position."""

    symbol: str
    weight: Decimal
    reason: str = ""


Order = BracketIntent | TargetWeight


@dataclass(frozen=True)
class PortfolioSnapshot:
    """What a strategy is allowed to know about its own book at the close of `as_of`."""

    as_of: date
    equity: Decimal
    cash: Decimal
    sizable_cash: Decimal
    """Cash minus the tax reserve. The reserve is real money that must not be traded."""
    positions: dict[str, Decimal]
    blacklist: frozenset[str]
    stops: dict[str, Decimal] = field(default_factory=dict)
    """Each bracketed position's resting stop: what the portfolio-heat cap needs (lesson 03 §6)."""

    def holds(self, symbol: str) -> bool:
        return self.positions.get(symbol, Decimal(0)) > 0


@runtime_checkable
class Strategy(Protocol):
    name: str

    def on_close(self, view: DataView, book: PortfolioSnapshot) -> list[Order]:
        """Decide at the close of `view.today` what to place for the next session.

        `view` cannot return data after `view.today`; asking raises `FutureDataError`.
        """
        ...
