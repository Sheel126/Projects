"""The tax ledger: the one object the backtester and the fixtures both talk to (lesson 02 §5-§7).

It owns the lot book, the §1091 matcher, the blacklist and the liability account, and it enforces
the ordering those three have to agree on:

    buy   -> create the lot, then look back for loss sales this purchase just washed
    sell  -> dispose FIFO, match the "before" side of the window, then blacklist the symbol,
             and only then hand the *allowed* gain to the liability account

Getting that order wrong is how a disallowed loss ends up reducing tax.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from liquid_atm_quant.tax.lots import Disposal, ExitReason, Lot, LotBook, Trade
from liquid_atm_quant.tax.money import ZERO, cents, money
from liquid_atm_quant.tax.reserve import ReserveSnapshot, TaxAccount, TaxRates
from liquid_atm_quant.tax.wash import WASH_WINDOW_DAYS, WashSaleMatcher, blacklist_until


@dataclass(frozen=True)
class TaxConfig:
    lot_method: str = "FIFO"
    short_term_rate: Decimal = Decimal("0.32")
    long_term_rate: Decimal = Decimal("0.15")
    qualified_dividend_rate: Decimal = Decimal("0.15")
    wash_window_days: int = WASH_WINDOW_DAYS
    blacklist_days: int = 31
    payment_schedule: str = "quarterly"
    same_lot_remainder_is_replacement: bool = True

    @staticmethod
    def from_dict(raw: dict) -> "TaxConfig":
        """Accepts the fixture `config` block, where the reserve rate is named `tax_reserve_rate`."""
        short_term = raw.get("short_term_rate", raw.get("tax_reserve_rate", "0.32"))
        return TaxConfig(
            lot_method=raw.get("lot_method", "FIFO"),
            short_term_rate=money(short_term),
            long_term_rate=money(raw.get("long_term_rate", "0.15")),
            qualified_dividend_rate=money(raw.get("qualified_dividend_rate", "0.15")),
            wash_window_days=int(raw.get("wash_window_days", WASH_WINDOW_DAYS)),
            blacklist_days=int(raw.get("blacklist_days", 31)),
            payment_schedule=raw.get("payment_schedule", "none"),
            same_lot_remainder_is_replacement=bool(
                raw.get("same_lot_remainder_is_replacement", True)))


@dataclass
class BlacklistEntry:
    symbol: str
    reason: str
    blacklisted_on: date
    until_date: date            # tradable again ON this date
    source_disposal_id: int | None = None


@dataclass
class LedgerState:
    """A flat snapshot, shaped like the fixture `expected` block so comparison is direct."""

    realized_gain: Decimal
    disallowed_losses: list[dict] = field(default_factory=list)
    open_lots: list[dict] = field(default_factory=list)
    tax_reserve: Decimal = ZERO
    blacklist: list[dict] = field(default_factory=list)
    carryforward: Decimal = ZERO
    deferred_loss_balance: Decimal = ZERO


class TaxLedger:
    def __init__(self, config: TaxConfig | None = None) -> None:
        self.config = config or TaxConfig()
        self.book = LotBook(self.config.lot_method)
        self.matcher = WashSaleMatcher(
            self.config.wash_window_days, self.config.same_lot_remainder_is_replacement)
        self.account = TaxAccount(
            TaxRates(self.config.short_term_rate, self.config.long_term_rate,
                     self.config.qualified_dividend_rate),
            payment_schedule=self.config.payment_schedule)
        self.blacklist: dict[str, BlacklistEntry] = {}
        self._next_fill_id = 1
        self._last_date: date | None = None
        self.dividends_received = ZERO

    # ---- trades ----------------------------------------------------------------------

    def buy(self, when: date, symbol: str, quantity: object, price: object,
            fees: object = 0) -> Lot:
        trade = Trade.of(when, symbol, "buy", quantity, price, fees, self._take_fill_id())
        return self.apply(trade)[0]

    def sell(self, when: date, symbol: str, quantity: object, price: object, fees: object = 0,
             exit_reason: ExitReason | None = None) -> list[Disposal]:
        trade = Trade.of(when, symbol, "sell", quantity, price, fees, self._take_fill_id(),
                         exit_reason)
        return self.apply(trade)

    def apply(self, trade: Trade) -> list:
        """Apply one fill. Returns `[Lot]` for a buy or the list of `Disposal`s for a sell."""
        self._advance(trade.date)
        if trade.side == "buy":
            lot = self.book.acquire(trade)
            # A purchase can retroactively disallow a loss taken in the previous 30 days. Any
            # disposal it touches has already been reported to the account, so re-report the delta.
            before = {d.disposal_id: d.disallowed_loss for d in self.book.disposals}
            self.matcher.on_acquire(self.book, lot)
            for disposal in self.book.disposals:
                delta = disposal.disallowed_loss - before.get(disposal.disposal_id, ZERO)
                if delta != 0:
                    # The loss shrinks, so the allowed gain rises by the same amount.
                    self.account.realize(disposal.disposed_on, delta, disposal.is_long_term)
            return [lot]

        disposals = self.book.dispose(trade)
        self.matcher.on_dispose(self.book, disposals)
        for disposal in disposals:
            self.account.realize(disposal.disposed_on, disposal.allowed_gain, disposal.is_long_term)
            if disposal.gain < 0:
                self._blacklist(disposal)
        return disposals

    def split(self, when: date, symbol: str, ratio: object) -> None:
        """Restate open lots for a split (see `LotBook.split`). Basis and dates are unchanged."""
        self._advance(when)
        self.book.split(symbol, money(ratio))

    def dividend(self, when: date, amount: object, qualified: bool = True) -> None:
        self._advance(when)
        self.account.dividend(when, cents(amount), qualified)
        self.dividends_received = cents(self.dividends_received + cents(amount))

    # ---- calendar --------------------------------------------------------------------

    def settle(self, today: date) -> Decimal:
        """Pay any estimated tax due. Returns the cash that left the account."""
        self._advance(today)
        return self.account.settle(today)

    def _advance(self, when: date) -> None:
        if self._last_date is not None and when < self._last_date:
            raise ValueError(f"trades must arrive in date order: {when} after {self._last_date}")
        self._last_date = when
        for symbol, entry in list(self.blacklist.items()):
            if when >= entry.until_date:
                del self.blacklist[symbol]

    def is_blacklisted(self, symbol: str, when: date) -> bool:
        entry = self.blacklist.get(symbol)
        return entry is not None and when < entry.until_date

    def _blacklist(self, disposal: Disposal) -> None:
        until = blacklist_until(disposal.disposed_on, self.config.blacklist_days)
        current = self.blacklist.get(disposal.symbol)
        if current is None or until > current.until_date:
            self.blacklist[disposal.symbol] = BlacklistEntry(
                disposal.symbol, "wash_sale_cooldown", disposal.disposed_on, until,
                disposal.disposal_id)

    def _take_fill_id(self) -> int:
        fill_id = self._next_fill_id
        self._next_fill_id += 1
        return fill_id

    # ---- reporting -------------------------------------------------------------------

    @property
    def realized_gain(self) -> Decimal:
        """Allowed realized gain/loss to date: what a 1099-B would show."""
        return cents(sum((d.allowed_gain for d in self.book.disposals), ZERO))

    @property
    def gross_realized_gain(self) -> Decimal:
        """Before §1091. The gap to `realized_gain` is the deferred loss balance."""
        return cents(sum((d.gain for d in self.book.disposals), ZERO))

    @property
    def deferred_loss_balance(self) -> Decimal:
        """Losses §1091 pushed into the basis of shares still held (positive = deferred)."""
        return cents(sum((lot.wash_adjustment for lot in self.book.lots if lot.is_open), ZERO))

    def reserve(self, as_of: date | None = None) -> Decimal:
        return self.account.reserve(as_of or self._last_date or date.min)

    def snapshot(self, equity: Decimal, as_of: date | None = None) -> ReserveSnapshot:
        when = as_of or self._last_date or date.min
        return ReserveSnapshot(when, cents(equity), self.reserve(when),
                               self.account.carryforward(when), self.account.ordinary_offset(when),
                               cents(sum(self.account.paid.values(), ZERO)))

    def state(self, as_of: date | None = None) -> LedgerState:
        when = as_of or self._last_date or date.min
        return LedgerState(
            realized_gain=self.realized_gain,
            disallowed_losses=[
                {"sell_date": d.disposed_on.isoformat(), "symbol": d.symbol,
                 "amount": d.disallowed_loss}
                for d in self.book.disposals if d.disallowed_loss > 0],
            open_lots=[
                {"symbol": lot.symbol, "qty": lot.qty_remaining, "cost_basis": lot.basis_remaining,
                 "acquired": lot.acquired_on.isoformat(),
                 "holding_period_start": lot.holding_period_start.isoformat()}
                for lot in sorted((x for x in self.book.lots if x.is_open),
                                  key=lambda x: (x.symbol, x.acquired_on, x.lot_id))],
            tax_reserve=self.reserve(when),
            blacklist=[{"symbol": e.symbol, "until": e.until_date.isoformat()}
                       for e in sorted(self.blacklist.values(), key=lambda e: e.symbol)],
            carryforward=self.account.carryforward(when),
            deferred_loss_balance=self.deferred_loss_balance)
