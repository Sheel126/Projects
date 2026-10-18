"""Portfolio construction (lesson 03 §6): from ranked candidates to sized brackets.

Fixed-fractional risk sizes each trade, then four limits decide how many get through, in order:

    position   notional <= 15% of equity     one name that gaps through its stop
    heat       open risk to stops <= 6%      everything stopping out on the same day
    sector     <= 3 positions per sector     ten "different" names that are one trade
    pacing     <= 3 new entries a day        one day's signals filling the whole book

Heat is measured from today's close to each resting stop, not from the entry. With fixed brackets
that is exactly what is lost if every stop fills now, so a winner that has run far above its stop
uses *more* of the budget than it did on entry. Gaps make the real figure worse than this; heat is
the floor on a bad day, not the ceiling (§6).

The result is a `BracketIntent` with an explicit `notional`. The engine then applies its own ADV
and cash caps, which can only shrink a position, so the heat accounting here stays conservative.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from liquid_atm_quant.backtest.strategy import BracketIntent, PortfolioSnapshot
from liquid_atm_quant.strategy.params import FunnelParams
from liquid_atm_quant.strategy.regime import Regime
from liquid_atm_quant.strategy.screener import Candidate
from liquid_atm_quant.tax.money import ZERO, cents

SKIP_REASONS = ("slots", "pacing", "sector", "heat", "too_small")


@dataclass
class BookResult:
    intents: list[BracketIntent]
    heat_before: Decimal
    heat_after: Decimal
    skipped: dict[str, int] = field(default_factory=lambda: dict.fromkeys(SKIP_REASONS, 0))


def open_heat(book: PortfolioSnapshot, marks: dict[str, float]) -> Decimal:
    """Dollars lost if every resting stop filled at its level right now."""
    total = ZERO
    for symbol, quantity in book.positions.items():
        stop = book.stops.get(symbol)
        mark = marks.get(symbol)
        if stop is None or mark is None or mark != mark:      # mark != mark: NaN
            continue
        total += max(ZERO, cents(quantity * (Decimal(repr(mark)) - stop)))
    return total


def build(candidates: list[Candidate], book: PortfolioSnapshot, regime: Regime,
          marks: dict[str, float], sectors: dict[str, str], p: FunnelParams,
          min_notional: Decimal = Decimal("100.00")) -> BookResult:
    heat = open_heat(book, marks)
    result = BookResult([], heat, heat)
    if regime is Regime.RISK_OFF or not candidates:
        return result

    equity = book.equity
    caution = regime is Regime.CAUTION
    risk = Decimal(repr(p.risk_per_trade)) * (Decimal(repr(p.caution_risk_scale)) if caution
                                              else Decimal(1))
    new_cap = p.max_new_per_day_caution if caution else p.max_new_per_day
    max_heat = cents(equity * Decimal(repr(p.max_heat)))
    max_notional = cents(equity * Decimal(repr(p.max_position_weight)))

    held = [s for s, q in book.positions.items() if q > 0]
    slots = p.max_positions - len(held)
    per_sector: dict[str, int] = {}
    for symbol in held:
        sector = sectors.get(symbol, "Unknown")
        per_sector[sector] = per_sector.get(sector, 0) + 1

    for c in candidates:
        if slots <= 0:
            result.skipped["slots"] += 1
            continue
        if len(result.intents) >= new_cap:
            result.skipped["pacing"] += 1
            continue
        if per_sector.get(c.sector, 0) >= p.max_per_sector:
            result.skipped["sector"] += 1
            continue

        notional = min(cents(equity * risk / c.risk_per_share * c.entry_limit), max_notional)
        trade_risk = cents(notional / c.entry_limit * c.risk_per_share)
        if heat + trade_risk > max_heat:
            result.skipped["heat"] += 1
            continue
        if notional < min_notional:
            result.skipped["too_small"] += 1
            continue

        result.intents.append(BracketIntent(
            c.symbol, c.entry_limit, c.take_profit, c.stop_loss, risk_fraction=risk,
            reason=c.reason, regime=regime.value, time_stop_days=p.time_stop_days,
            notional=notional))
        heat += trade_risk
        slots -= 1
        per_sector[c.sector] = per_sector.get(c.sector, 0) + 1

    result.heat_after = heat
    return result
