"""Tax liability, carryforwards, the reserve and estimated-tax payments (lesson 02 §7).

Three things this models that a naive `reserve = rate * gains` does not:

1. **Netting is annual, not per trade.** A winning January followed by a losing February must not
   leave cash over-reserved, so the liability is recomputed from year-to-date figures.
2. **A net loss year does not refund cash.** Only $3,000 of a net capital loss is deductible
   against ordinary income per year; the rest carries forward indefinitely, keeping its
   short/long character. That tax shield is reported separately and is deliberately *not* credited
   to the strategy's equity, because it offsets income the strategy did not earn.
3. **The money actually leaves.** Estimated taxes are paid on the 1040-ES schedule, so the drag of
   losing that cash mid-year is in the equity curve rather than assumed away.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from liquid_atm_quant.tax.money import ZERO, cents, money

ORDINARY_DEDUCTION_LIMIT = Decimal("3000.00")

# 1040-ES: (due date, last day of the income period it covers). The fourth instalment for year Y
# is due 15 January of Y+1.
ESTIMATED_DUE_DATES: tuple[tuple[tuple[int, int], tuple[int, int], int], ...] = (
    ((4, 15), (3, 31), 0),
    ((6, 15), (5, 31), 0),
    ((9, 15), (8, 31), 0),
    ((1, 15), (12, 31), 1),     # due in the following calendar year
)


@dataclass(frozen=True)
class TaxRates:
    short_term: Decimal = Decimal("0.32")       # ordinary income: ~24% federal + ~8% state
    long_term: Decimal = Decimal("0.15")
    qualified_dividend: Decimal = Decimal("0.15")

    @staticmethod
    def of(short_term: object = "0.32", long_term: object = "0.15",
           qualified_dividend: object = "0.15") -> "TaxRates":
        return TaxRates(money(short_term), money(long_term), money(qualified_dividend))


@dataclass
class YearResult:
    year: int
    short_term_net: Decimal          # after carry-ins and cross-netting; can be negative
    long_term_net: Decimal
    dividends: Decimal
    ordinary_dividends: Decimal
    tax: Decimal                     # what is owed for the year, floored at zero
    ordinary_offset: Decimal         # value of the <=$3,000 deduction; reported, not credited
    short_term_carryout: Decimal     # positive magnitudes carried into the next year
    long_term_carryout: Decimal
    is_final: bool                   # False while the year is still in progress


@dataclass
class _Event:
    when: date
    short_term: Decimal = ZERO
    long_term: Decimal = ZERO
    dividend: Decimal = ZERO             # qualified: taxed at the long-term-style dividend rate
    ordinary_dividend: Decimal = ZERO    # holding period too short to qualify: ordinary income


class TaxAccount:
    """Running liability for one taxable account.

    `payment_schedule`:
      * `quarterly` — 1040-ES instalments (the realistic default).
      * `annual`    — the whole year settles on 15 April of the following year.
      * `none`      — nothing is ever paid; used by the fixtures, which assert on the reserve.
    """

    def __init__(self, rates: TaxRates | None = None, payment_schedule: str = "quarterly") -> None:
        if payment_schedule not in ("quarterly", "annual", "none"):
            raise ValueError(f"unknown payment_schedule {payment_schedule!r}")
        self.rates = rates or TaxRates()
        self.payment_schedule = payment_schedule
        self._events: list[_Event] = []
        self._by_year: dict[int, list[_Event]] = {}
        self._years_cache: tuple[tuple[date, int], dict[int, YearResult]] | None = None
        self.paid: dict[int, Decimal] = {}          # tax year -> cash already sent to the IRS
        self.payments: list[tuple[date, int, Decimal]] = []
        self._settled_through: date | None = None

    # ---- recording -------------------------------------------------------------------

    def realize(self, when: date, amount: Decimal, long_term: bool) -> None:
        """Record an allowed (post-§1091) realized gain or loss."""
        self._record(_Event(when, long_term=cents(amount)) if long_term
                     else _Event(when, short_term=cents(amount)))

    def dividend(self, when: date, amount: Decimal, qualified: bool = True) -> None:
        """A distribution. Unqualified dividends (holding period 60 days or less around the
        ex-date) are ordinary income: they are taxed at the ordinary rate and, unlike capital
        gains, cannot be offset by capital losses. A swing bot collects mostly these."""
        self._record(_Event(when, dividend=cents(amount)) if qualified
                     else _Event(when, ordinary_dividend=cents(amount)))

    def _record(self, event: _Event) -> None:
        self._events.append(event)
        self._by_year.setdefault(event.when.year, []).append(event)
        self._years_cache = None

    # ---- computation -----------------------------------------------------------------

    def years(self, through: date) -> dict[int, YearResult]:
        """Net every tax year up to `through`, threading carryforwards forward in order."""
        if not self._events:
            return {}
        key = (through, len(self._events))
        if self._years_cache is not None and self._years_cache[0] == key:
            return self._years_cache[1]
        first = min(self._by_year)
        out: dict[int, YearResult] = {}
        st_carry = lt_carry = ZERO
        for year in range(first, through.year + 1):
            events = [e for e in self._by_year.get(year, ()) if e.when <= through]
            result = self._net_year(year, events, st_carry, lt_carry,
                                   is_final=date(year, 12, 31) <= through)
            out[year] = result
            st_carry, lt_carry = result.short_term_carryout, result.long_term_carryout
        self._years_cache = (key, out)
        return out

    def _net_year(self, year: int, events: list[_Event], st_carry: Decimal, lt_carry: Decimal,
                  is_final: bool) -> YearResult:
        st = sum((e.short_term for e in events), ZERO) - st_carry
        lt = sum((e.long_term for e in events), ZERO) - lt_carry
        dividends = sum((e.dividend for e in events), ZERO)
        ordinary_dividends = sum((e.ordinary_dividend for e in events), ZERO)

        # Cross-netting: a net loss in one category offsets a net gain in the other.
        if st < 0 and lt > 0:
            used = min(-st, lt)
            st, lt = st + used, lt - used
        elif lt < 0 and st > 0:
            used = min(-lt, st)
            lt, st = lt + used, st - used

        # Dividends sit outside the capital-loss netting on purpose: a capital loss cannot
        # shelter dividend income beyond the $3,000 ordinary-income deduction.
        tax = cents(max(st, ZERO) * self.rates.short_term
                    + max(lt, ZERO) * self.rates.long_term
                    + dividends * self.rates.qualified_dividend
                    + ordinary_dividends * self.rates.short_term)

        overall = st + lt
        ordinary_offset = st_out = lt_out = ZERO
        if overall < 0:
            deduction = min(ORDINARY_DEDUCTION_LIMIT, -overall)
            ordinary_offset = cents(deduction * self.rates.short_term)
            # Short-term losses are spent on the ordinary-income deduction first: they are the
            # more valuable kind to carry forward, since they offset the higher rate.
            st_loss, lt_loss = max(-st, ZERO), max(-lt, ZERO)
            used_st = min(deduction, st_loss)
            st_out, lt_out = st_loss - used_st, lt_loss - (deduction - used_st)
        return YearResult(year, cents(st), cents(lt), dividends, ordinary_dividends, tax,
                          ordinary_offset, cents(st_out), cents(lt_out), is_final)

    def liability(self, through: date) -> Decimal:
        """Total tax owed for every year up to `through`, whether or not it has been paid."""
        return cents(sum((r.tax for r in self.years(through).values()), ZERO))

    def reserve(self, through: date) -> Decimal:
        """Cash that must be held back: liability accrued so far, less what has been paid."""
        paid = sum(self.paid.values(), ZERO)
        return max(ZERO, cents(self.liability(through) - paid))

    def ordinary_offset(self, through: date) -> Decimal:
        """Cumulative value of the $3,000-per-year deduction. Reported, never added to equity."""
        return cents(sum((r.ordinary_offset for r in self.years(through).values()), ZERO))

    def carryforward(self, through: date) -> Decimal:
        """Loss carried into the next year (both characters), as a positive magnitude."""
        results = self.years(through)
        if not results:
            return ZERO
        last = results[max(results)]
        return cents(last.short_term_carryout + last.long_term_carryout)

    # ---- payments --------------------------------------------------------------------

    def settle(self, today: date) -> Decimal:
        """Pay anything due on or before `today`. Returns the cash that left the account."""
        if self.payment_schedule == "none":
            self._settled_through = today
            return ZERO
        start = self._settled_through
        self._settled_through = today
        total = ZERO
        for due, year, period_end in self._due_dates(start, today):
            owed = self._owed_for_period(year, period_end)
            already = self.paid.get(year, ZERO)
            payment = cents(max(ZERO, owed - already))
            if payment > 0:
                self.paid[year] = already + payment
                self.payments.append((due, year, payment))
                total += payment
        return total

    def _due_dates(self, after: date | None, through: date) -> list[tuple[date, int, date]]:
        """(due date, tax year, last day of the covered income period), in chronological order."""
        if not self._events:
            return []
        first_year = min(e.when.year for e in self._events)
        out: list[tuple[date, int, date]] = []
        for year in range(first_year, through.year + 1):
            if self.payment_schedule == "annual":
                out.append((date(year + 1, 4, 15), year, date(year, 12, 31)))
                continue
            for (due_m, due_d), (end_m, end_d), year_offset in ESTIMATED_DUE_DATES:
                out.append((date(year + year_offset, due_m, due_d), year, date(year, end_m, end_d)))
            # The 15 April true-up settles anything the instalments under-withheld.
            out.append((date(year + 1, 4, 15), year, date(year, 12, 31)))
        out.sort()
        return [row for row in out if row[0] <= through and (after is None or row[0] > after)]

    def _owed_for_period(self, year: int, period_end: date) -> Decimal:
        """Liability for `year` counting only income through `period_end`."""
        results = self.years(period_end)
        return results[year].tax if year in results else ZERO


@dataclass
class ReserveSnapshot:
    """What the operator sees, and what Phase 6 will expose as "Available to Withdraw"."""

    as_of: date
    equity: Decimal
    reserve: Decimal
    carryforward: Decimal = ZERO
    ordinary_offset: Decimal = ZERO
    paid_to_date: Decimal = ZERO

    @property
    def available_to_withdraw(self) -> Decimal:
        return cents(self.equity - self.reserve)
