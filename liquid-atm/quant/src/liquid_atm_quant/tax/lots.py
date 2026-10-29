"""Tax lots, disposals, FIFO matching and the holding-period test (lesson 02 §5).

The invariant that keeps this engine honest about pennies: a lot's *remaining* basis is carried
explicitly, and the final disposal of a lot consumes exactly what is left rather than a rounded
share of the original. Wash-sale adjustments can raise a lot's basis after part of it has already
been sold, so a "basis per share" computed once at acquisition would drift.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from liquid_atm_quant.tax.money import ZERO, allocate, cents, qty as as_qty

Side = Literal["buy", "sell"]
ExitReason = Literal["take_profit", "stop_loss", "time_stop", "december_flush", "kill_switch",
                     "manual", "rebalance", "terminal_liquidation", "delisted"]


@dataclass(frozen=True)
class Trade:
    """One fill. `fill_id` must be monotonic: it is the tie-break that makes FIFO deterministic."""

    date: date
    symbol: str
    side: Side
    qty: Decimal
    price: Decimal
    fees: Decimal = ZERO
    fill_id: int = 0
    exit_reason: ExitReason | None = None

    @staticmethod
    def of(trade_date: date, symbol: str, side: Side, quantity: object, price: object,
           fees: object = 0, fill_id: int = 0, exit_reason: ExitReason | None = None) -> "Trade":
        return Trade(trade_date, symbol, side, as_qty(quantity), cents(price), cents(fees),
                     fill_id, exit_reason)


@dataclass
class Lot:
    lot_id: int
    symbol: str
    acquired_on: date
    holding_period_start: date          # earlier than acquired_on when a washed loss tacked on
    qty_original: Decimal
    qty_remaining: Decimal
    basis_remaining: Decimal            # basis attached to qty_remaining, incl. wash adjustments
    basis_original: Decimal
    wash_adjustment: Decimal = ZERO
    open_fill_id: int = 0
    closed_on: date | None = None
    qty_used_as_replacement: Decimal = ZERO   # shares already absorbing a disallowed loss

    @property
    def is_open(self) -> bool:
        return self.qty_remaining > 0

    @property
    def replacement_capacity(self) -> Decimal:
        """Shares of this lot still able to absorb a disallowed loss.

        Capacity is against `qty_original`, not `qty_remaining`: §1091 keys off the *acquisition*,
        so a lot that has since been partly sold was still a replacement purchase.
        """
        return self.qty_original - self.qty_used_as_replacement


@dataclass
class Disposal:
    disposal_id: int
    lot_id: int
    symbol: str
    disposed_on: date
    close_fill_id: int
    qty: Decimal
    proceeds: Decimal                   # net of the sell-side fees allocated to this slice
    cost_basis: Decimal
    gain: Decimal                       # proceeds - cost_basis; negative is a loss
    is_long_term: bool
    acquired_on: date
    holding_period_start: date
    exit_reason: ExitReason | None = None
    disallowed_loss: Decimal = ZERO
    qty_washed: Decimal = ZERO          # shares already matched to replacement stock
    wash_matches: list[tuple[int, Decimal, Decimal]] = field(default_factory=list)
    """(replacement_lot_id, qty, disallowed_amount) — the wash_sale_adjustments rows."""

    @property
    def allowed_gain(self) -> Decimal:
        """What actually hits the tax return: the loss net of anything §1091 disallowed."""
        return self.gain + self.disallowed_loss


def plus_one_year(d: date) -> date:
    """The anniversary. 2028-02-29 + 1y is 2029-02-28 (there is no 2029-02-29)."""
    try:
        return d.replace(year=d.year + 1)
    except ValueError:
        return d.replace(year=d.year + 1, month=2, day=28)


def is_long_term(holding_period_start: date, disposed_on: date) -> bool:
    """§1222: the holding period starts the day *after* acquisition and must exceed one year.

    Bought 03-02, the anniversary is next year's 03-02: selling *on* it is still short term.
    """
    return disposed_on > plus_one_year(holding_period_start)


class LotBook:
    """The open-lot inventory for one account, plus the full disposal history."""

    def __init__(self, lot_method: str = "FIFO") -> None:
        if lot_method.upper() != "FIFO":
            raise ValueError(f"only FIFO is supported (Alpaca's default); got {lot_method!r}")
        self.lots: list[Lot] = []
        self.disposals: list[Disposal] = []
        self._next_lot_id = 1
        self._next_disposal_id = 1

    # ---- buys ------------------------------------------------------------------------

    def acquire(self, trade: Trade) -> Lot:
        """A buy fill becomes one lot. Fees are capitalised into basis, which is what they are."""
        basis = cents(trade.qty * trade.price + trade.fees)
        lot = Lot(lot_id=self._next_lot_id, symbol=trade.symbol, acquired_on=trade.date,
                  holding_period_start=trade.date, qty_original=trade.qty, qty_remaining=trade.qty,
                  basis_remaining=basis, basis_original=basis, open_fill_id=trade.fill_id)
        self._next_lot_id += 1
        self.lots.append(lot)
        return lot

    def split(self, symbol: str, ratio: Decimal) -> None:
        """A stock split: every open lot holds `ratio` times the shares at the same total basis.

        Not a disposal (IRC §1036): no gain, no new holding period. A 2-for-1 is `ratio` 2, a
        1-for-10 reverse split is 0.1."""
        for lot in self.lots:
            if lot.symbol == symbol and lot.is_open:
                lot.qty_original = as_qty(lot.qty_original * ratio)
                lot.qty_remaining = as_qty(lot.qty_remaining * ratio)
                lot.qty_used_as_replacement = as_qty(lot.qty_used_as_replacement * ratio)

    # ---- sells -----------------------------------------------------------------------

    def open_lots(self, symbol: str) -> list[Lot]:
        """FIFO order: oldest acquisition first, `(acquired_on, lot_id)` as the tie-break."""
        return sorted((lot for lot in self.lots if lot.symbol == symbol and lot.is_open),
                      key=lambda lot: (lot.acquired_on, lot.lot_id))

    def position(self, symbol: str) -> Decimal:
        return sum((lot.qty_remaining for lot in self.lots if lot.symbol == symbol), ZERO)

    def dispose(self, trade: Trade) -> list[Disposal]:
        """Consume lots FIFO for a sell fill. Returns one Disposal per lot touched.

        Sell-side fees reduce proceeds (they are not a separate deduction), allocated across the
        consumed lots pro rata by quantity with the rounding residual on the last slice.
        """
        available = self.open_lots(trade.symbol)
        held = sum((lot.qty_remaining for lot in available), ZERO)
        if held < trade.qty:
            raise ValueError(f"cannot sell {trade.qty} {trade.symbol}: only {held} held "
                             f"(the backtester must never short)")

        # First pass: how much comes from each lot, so fees can be allocated before any mutation.
        slices: list[tuple[Lot, Decimal]] = []
        remaining = trade.qty
        for lot in available:
            if remaining <= 0:
                break
            take = min(remaining, lot.qty_remaining)
            slices.append((lot, take))
            remaining -= take

        takes = [take for _, take in slices]
        fee_slices = allocate(trade.fees, takes)
        gross_slices = allocate(cents(trade.qty * trade.price), takes)

        out: list[Disposal] = []
        for (lot, take), fee, gross in zip(slices, fee_slices, gross_slices, strict=True):
            basis = lot.basis_remaining if take == lot.qty_remaining \
                else cents(lot.basis_remaining * take / lot.qty_remaining)
            proceeds = gross - fee
            lot.qty_remaining -= take
            lot.basis_remaining -= basis
            if lot.qty_remaining == 0:
                lot.closed_on = trade.date
                lot.basis_remaining = ZERO      # guard against a stray rounding crumb

            disposal = Disposal(
                disposal_id=self._next_disposal_id, lot_id=lot.lot_id, symbol=trade.symbol,
                disposed_on=trade.date, close_fill_id=trade.fill_id, qty=take, proceeds=proceeds,
                cost_basis=basis, gain=cents(proceeds - basis),
                is_long_term=is_long_term(lot.holding_period_start, trade.date),
                acquired_on=lot.acquired_on, holding_period_start=lot.holding_period_start,
                exit_reason=trade.exit_reason)
            self._next_disposal_id += 1
            self.disposals.append(disposal)
            out.append(disposal)
        return out

    # ---- wash-sale support -----------------------------------------------------------

    def lots_acquired_between(self, symbol: str, start: date, end: date) -> list[Lot]:
        """Acquisition-date window, inclusive, in §1091 matching order (oldest first)."""
        return sorted((lot for lot in self.lots
                       if lot.symbol == symbol and start <= lot.acquired_on <= end),
                      key=lambda lot: (lot.acquired_on, lot.lot_id))

    def add_basis(self, lot: Lot, amount: Decimal, washed_holding_days: int) -> None:
        """Apply a §1091(d) adjustment: basis up, holding period tacked back."""
        lot.basis_original += amount
        lot.basis_remaining += amount
        lot.wash_adjustment += amount
        tacked = lot.acquired_on - timedelta(days=washed_holding_days)
        lot.holding_period_start = min(lot.holding_period_start, tacked)


__all__ = ["Trade", "Lot", "Disposal", "LotBook", "Side", "ExitReason",
           "is_long_term", "plus_one_year"]
