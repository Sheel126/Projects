"""Transaction costs (lesson 02 §4).

Alpaca charges no commission, so what is left is stop slippage plus two sell-side regulatory fees.
Both fee rates are reset by the regulators (SEC Section 31 annually, FINRA periodically), so they
live here as configuration with a documented default rather than as constants in the engine.
Verify them against Alpaca's current fee schedule before trusting a live P&L.
"""

from dataclasses import dataclass
from decimal import Decimal

from liquid_atm_quant.tax.money import ZERO, cents, money

TICK = Decimal("0.01")


@dataclass(frozen=True)
class CostModel:
    slippage_bps: Decimal = Decimal("5")
    """Applied to a stop that triggers intrabar, because a stop becomes a market order. Zero for
    limit fills (entry and take profit): a limit gets its price or better, by definition."""

    sec_fee_per_million: Decimal = Decimal("27.80")
    """SEC Section 31, on the *proceeds* of a sale only. Rate changes annually."""

    finra_taf_per_share: Decimal = Decimal("0.000166")
    finra_taf_cap: Decimal = Decimal("8.30")
    """FINRA Trading Activity Fee, per share sold, capped per trade. Sells only."""

    tick: Decimal = TICK

    def sell_fees(self, proceeds: object, quantity: object) -> Decimal:
        """Regulatory fees on one sell fill. They reduce proceeds, so the tax engine sees them."""
        gross = cents(proceeds)
        qty = money(quantity)
        sec = gross * self.sec_fee_per_million / Decimal("1000000")
        taf = min(qty * self.finra_taf_per_share, self.finra_taf_cap)
        return cents(sec + taf)

    def buy_fees(self, notional: object, quantity: object) -> Decimal:
        """Nothing: the regulatory fees are sell-side, and Alpaca's commission is zero."""
        return ZERO

    def stop_slippage(self, price: object) -> Decimal:
        """How much worse than the stop price a triggered stop actually fills.

        At least one tick, because "filled exactly at the stop" is not a thing that happens on the
        days a stop matters.
        """
        return max(self.tick, cents(money(price) * self.slippage_bps / Decimal("10000")))


ZERO_COSTS = CostModel(slippage_bps=Decimal("0"), sec_fee_per_million=Decimal("0"),
                       finra_taf_per_share=Decimal("0"), tick=Decimal("0"))
"""Frictionless, for isolating engine bugs from cost effects in tests."""
