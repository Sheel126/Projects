"""IRC §1091 wash-sale matching (lesson 02 §6).

Two hooks, because the 61-day window reaches in both directions:

* `on_dispose` — a loss sale looks back at purchases already made in the previous 30 days.
  This is the side the 31-day blacklist *cannot* prevent, and the side the bot's own tranche
  scaling creates (lesson 02 §6).
* `on_acquire` — a new purchase looks back at loss sales in the previous 30 days whose loss is
  still unmatched, and retroactively disallows them. This is why a disposal's `disallowed_loss`
  is not final at the moment of the sale.

Matching is share for share: selling 100 at a $500 loss and buying 40 replacement shares
disallows exactly $200.
"""

from datetime import date, timedelta
from decimal import Decimal

from liquid_atm_quant.tax.lots import Disposal, Lot, LotBook
from liquid_atm_quant.tax.money import ZERO, cents

WASH_WINDOW_DAYS = 30


class WashSaleMatcher:
    """Stateless apart from its configuration; all state lives on the lots and disposals."""

    def __init__(self, window_days: int = WASH_WINDOW_DAYS,
                 same_lot_remainder_is_replacement: bool = True) -> None:
        self.window_days = window_days
        # Sell 50 of a 100-share lot bought 10 days ago at a loss: are the 50 you still hold
        # "replacement shares"? Pub. 550's reading says yes, and that is the pessimistic answer
        # (the loss is deferred), so it is the default. Phase 4 can measure the other reading.
        self.same_lot_remainder_is_replacement = same_lot_remainder_is_replacement
        self.skipped_prior_sale: list[tuple[int, int]] = []
        """(disposal_id, lot_id) for the documented limitation in lesson 02 §6: a replacement
        acquired inside the window but already sold before the loss sale. Adjusting it would mean
        rewriting an earlier disposal, so we skip it and record that it happened."""

    # ---- hooks -----------------------------------------------------------------------

    def on_dispose(self, book: LotBook, disposals: list[Disposal]) -> None:
        for disposal in sorted(disposals, key=lambda d: d.disposal_id):
            if disposal.gain >= 0:
                continue
            start = disposal.disposed_on - timedelta(days=self.window_days)
            candidates = book.lots_acquired_between(disposal.symbol, start, disposal.disposed_on)
            self._match(book, disposal, candidates)

    def on_acquire(self, book: LotBook, lot: Lot) -> None:
        """A purchase can disallow a loss taken up to `window_days` ago."""
        earliest_sale = lot.acquired_on - timedelta(days=self.window_days)
        pending = [d for d in book.disposals
                   if d.symbol == lot.symbol and d.gain < 0
                   and earliest_sale <= d.disposed_on <= lot.acquired_on
                   and d.qty_washed < d.qty]
        for disposal in sorted(pending, key=lambda d: d.disposal_id):
            self._match(book, disposal, [lot])

    # ---- the matcher -----------------------------------------------------------------

    def _match(self, book: LotBook, disposal: Disposal, candidates: list[Lot]) -> None:
        loss = -disposal.gain                       # positive magnitude
        for lot in candidates:
            unmatched = disposal.qty - disposal.qty_washed
            if unmatched <= 0:
                return
            capacity = self._capacity(disposal, lot)
            if capacity <= 0:
                continue
            matched = min(unmatched, capacity)

            # Exact when the whole loss is washed: no penny may vanish into a ratio.
            if disposal.qty_washed + matched == disposal.qty:
                amount = loss - disposal.disallowed_loss
            else:
                amount = cents(loss * matched / disposal.qty)
            if amount <= 0:
                continue

            washed_days = (disposal.disposed_on - disposal.holding_period_start).days
            book.add_basis(lot, amount, washed_days)
            lot.qty_used_as_replacement += matched
            disposal.qty_washed += matched
            disposal.disallowed_loss += amount
            disposal.wash_matches.append((lot.lot_id, matched, amount))

    def _capacity(self, disposal: Disposal, lot: Lot) -> Decimal:
        """How many of `lot`'s shares may absorb this disposal's loss."""
        if lot.acquired_on > disposal.disposed_on:
            # Acquired after the sale: the whole lot is replacement stock.
            return lot.replacement_capacity
        # Acquired on or before the sale, so it must still have been held at the sale.
        if lot.closed_on is not None and lot.closed_on < disposal.disposed_on:
            self.skipped_prior_sale.append((disposal.disposal_id, lot.lot_id))
            return ZERO
        if lot.lot_id == disposal.lot_id:
            if not self.same_lot_remainder_is_replacement:
                return ZERO
            # Only the shares still held can be replacements; the sold slice replaces nothing.
            return min(lot.replacement_capacity, lot.qty_remaining)
        return lot.replacement_capacity


def blacklist_until(sale_date: date, days: int = 31) -> date:
    """Tradable again *on* this date: `days` after a loss sale clears the 30-day "after" window."""
    return sale_date + timedelta(days=days)
