"""Unit tests for the tax engine, beneath the fixture layer (lesson 02 §5-§7).

The fixtures in `shared/tax-fixtures/` are the cross-language contract; these tests cover the parts
a fixture would express awkwardly - error paths, the rounding invariants, the retroactive-wash
ordering, and the estimated-tax calendar.
"""

from datetime import date
from decimal import Decimal

import pytest

from liquid_atm_quant.tax.fixtures import run_all
from liquid_atm_quant.tax.ledger import TaxConfig, TaxLedger
from liquid_atm_quant.tax.lots import LotBook, Trade, is_long_term, plus_one_year
from liquid_atm_quant.tax.money import allocate, cents
from liquid_atm_quant.tax.reserve import TaxAccount, TaxRates

D = Decimal
NO_PAY = TaxConfig(short_term_rate=D("0.32"), payment_schedule="none")


# ---- every fixture, as a test ----------------------------------------------------------------

@pytest.mark.parametrize("result", run_all(), ids=lambda r: r.name)
def test_fixture(result):
    """The golden vectors the Phase 6 Java ledger must also pass."""
    assert result.passed, result.report()


# ---- holding period --------------------------------------------------------------------------

def test_long_term_needs_more_than_one_year():
    bought = date(2026, 3, 2)
    assert is_long_term(bought, date(2027, 3, 1)) is False
    assert is_long_term(bought, date(2027, 3, 2)) is False   # on the anniversary: still short
    assert is_long_term(bought, date(2027, 3, 3)) is True


def test_leap_day_anniversary_falls_back_to_february_28():
    assert plus_one_year(date(2028, 2, 29)) == date(2029, 2, 28)
    assert is_long_term(date(2028, 2, 29), date(2029, 2, 28)) is False
    assert is_long_term(date(2028, 2, 29), date(2029, 3, 1)) is True


# ---- money invariants ------------------------------------------------------------------------

def test_allocation_never_leaks_or_invents_a_penny():
    total = D("0.07")
    parts = allocate(total, [D("1"), D("1"), D("1")])
    assert sum(parts) == total
    assert parts == [D("0.02"), D("0.02"), D("0.03")]


def test_allocating_across_zero_weights_returns_zeros():
    assert allocate(D("5.00"), [D("0"), D("0")]) == [D("0.00"), D("0.00")]


def test_rounding_is_half_away_from_zero_like_java():
    assert cents("1.005") == D("1.01")
    assert cents("-1.005") == D("-1.01")


def test_a_lot_sold_in_slices_gives_back_exactly_its_basis():
    """Per-share basis is recomputed from what is left, so three partial sells cannot drift."""
    book = LotBook()
    lot = book.acquire(Trade.of(date(2026, 1, 5), "AAA", "buy", 3, "100.01"))
    original = lot.basis_original
    consumed = D("0.00")
    for day, quantity in [(6, 1), (7, 1), (8, 1)]:
        for disposal in book.dispose(Trade.of(date(2026, 1, day), "AAA", "sell", quantity, "110")):
            consumed += disposal.cost_basis
    assert consumed == original
    assert lot.basis_remaining == D("0.00")


# ---- guards ----------------------------------------------------------------------------------

def test_selling_more_than_held_is_refused():
    ledger = TaxLedger(NO_PAY)
    ledger.buy(date(2026, 1, 5), "AAA", 10, "100")
    with pytest.raises(ValueError, match="never short"):
        ledger.sell(date(2026, 1, 6), "AAA", 11, "100")


def test_trades_must_arrive_in_date_order():
    ledger = TaxLedger(NO_PAY)
    ledger.buy(date(2026, 3, 1), "AAA", 10, "100")
    with pytest.raises(ValueError, match="date order"):
        ledger.buy(date(2026, 2, 1), "AAA", 10, "100")


def test_only_fifo_is_accepted():
    with pytest.raises(ValueError, match="only FIFO"):
        LotBook("LIFO")


# ---- wash-sale mechanics ---------------------------------------------------------------------

def test_a_lot_cannot_wash_its_own_full_disposal():
    """Selling a whole lot at a loss with no other holding leaves the loss fully deductible."""
    ledger = TaxLedger(NO_PAY)
    ledger.buy(date(2026, 1, 5), "AAA", 10, "100")
    disposals = ledger.sell(date(2026, 2, 5), "AAA", 10, "90")
    assert disposals[0].disallowed_loss == D("0.00")
    assert ledger.realized_gain == D("-100.00")


def test_the_unsold_remainder_of_the_same_lot_is_replacement_stock_by_default():
    """Pub. 550's reading, and the pessimistic one: the loss is deferred (lesson 02 §6)."""
    ledger = TaxLedger(NO_PAY)
    ledger.buy(date(2026, 1, 5), "AAA", 100, "100")
    disposals = ledger.sell(date(2026, 1, 20), "AAA", 50, "90")
    assert disposals[0].disallowed_loss == D("500.00")
    assert ledger.realized_gain == D("0.00")


def test_the_other_reading_is_configurable():
    ledger = TaxLedger(TaxConfig(short_term_rate=D("0.32"), payment_schedule="none",
                                 same_lot_remainder_is_replacement=False))
    ledger.buy(date(2026, 1, 5), "AAA", 100, "100")
    disposals = ledger.sell(date(2026, 1, 20), "AAA", 50, "90")
    assert disposals[0].disallowed_loss == D("0.00")
    assert ledger.realized_gain == D("-500.00")


def test_a_rebuy_retroactively_disallows_a_loss_already_reported():
    """The loss is allowed when taken and disallowed later, so the reserve has to move back up."""
    ledger = TaxLedger(NO_PAY)
    ledger.buy(date(2026, 1, 5), "BBB", 100, "50")
    ledger.sell(date(2026, 3, 2), "BBB", 100, "60")          # +1,000 gain
    ledger.buy(date(2026, 4, 1), "AAA", 100, "100")
    ledger.sell(date(2026, 4, 20), "AAA", 100, "90")         # -1,000 loss, allowed for now
    assert ledger.reserve(date(2026, 4, 20)) == D("0.00")

    ledger.buy(date(2026, 5, 1), "AAA", 100, "92")           # inside the window: loss disallowed
    assert ledger.realized_gain == D("1000.00")
    assert ledger.reserve(date(2026, 5, 1)) == D("320.00")


def test_a_replacement_already_sold_before_the_loss_sale_is_skipped_and_recorded():
    """The documented limitation in lesson 02 §6: we do not rewrite an earlier disposal."""
    ledger = TaxLedger(NO_PAY)
    ledger.buy(date(2026, 1, 5), "AAA", 100, "100")          # lot 1
    ledger.buy(date(2026, 3, 2), "AAA", 100, "95")           # lot 2, inside the later window
    ledger.sell(date(2026, 3, 5), "AAA", 200, "90")          # closes both
    ledger.buy(date(2026, 3, 9), "AAA", 50, "88")            # lot 3
    disposals = ledger.sell(date(2026, 3, 20), "AAA", 50, "80")
    # Lot 2 was acquired inside the window but sold on 03-05, before this loss sale. Adjusting it
    # would mean rewriting the 03-05 disposal, so it is skipped - and the skip is recorded rather
    # than silently producing a wrong number.
    skipped_lots = {lot_id for _, lot_id in ledger.matcher.skipped_prior_sale}
    assert skipped_lots == {2}
    assert disposals[0].disallowed_loss == D("0.00")


def test_the_blacklist_expires_on_day_31():
    ledger = TaxLedger(NO_PAY)
    ledger.buy(date(2026, 3, 2), "AAA", 10, "100")
    ledger.sell(date(2026, 3, 20), "AAA", 10, "90")
    assert ledger.is_blacklisted("AAA", date(2026, 4, 19)) is True
    assert ledger.is_blacklisted("AAA", date(2026, 4, 20)) is False


# ---- reserve, carryforwards, payments --------------------------------------------------------

def test_the_three_thousand_limit_caps_the_ordinary_deduction():
    account = TaxAccount(TaxRates.of("0.32"), payment_schedule="none")
    account.realize(date(2026, 6, 1), D("-10000.00"), long_term=False)
    year = account.years(date(2026, 12, 31))[2026]
    assert year.tax == D("0.00")
    assert year.ordinary_offset == cents(D("3000") * D("0.32"))
    assert year.short_term_carryout == D("7000.00")


def test_a_capital_loss_carryforward_keeps_its_character_and_shields_the_next_year():
    account = TaxAccount(TaxRates.of("0.32", "0.15"), payment_schedule="none")
    account.realize(date(2026, 6, 1), D("-10000.00"), long_term=False)
    account.realize(date(2027, 6, 1), D("8000.00"), long_term=False)
    assert account.years(date(2027, 12, 31))[2027].tax == D("320.00")


def test_a_short_term_loss_offsets_a_long_term_gain_across_categories():
    account = TaxAccount(TaxRates.of("0.32", "0.15"), payment_schedule="none")
    account.realize(date(2026, 3, 1), D("-1000.00"), long_term=False)
    account.realize(date(2026, 6, 1), D("1000.00"), long_term=True)
    assert account.years(date(2026, 12, 31))[2026].tax == D("0.00")


def test_ordinary_dividends_are_not_sheltered_by_capital_losses():
    """A capital loss cannot offset dividend income beyond the $3,000 ordinary deduction."""
    account = TaxAccount(TaxRates.of("0.32", "0.15", "0.15"), payment_schedule="none")
    account.realize(date(2026, 3, 1), D("-5000.00"), long_term=False)
    account.dividend(date(2026, 6, 1), D("1000.00"), qualified=False)
    year = account.years(date(2026, 12, 31))[2026]
    assert year.tax == D("320.00")             # the dividend is still taxed at the ordinary rate
    assert year.ordinary_dividends == D("1000.00")


def test_qualified_and_ordinary_dividends_are_taxed_differently():
    qualified = TaxAccount(TaxRates.of("0.32", "0.15", "0.15"), payment_schedule="none")
    qualified.dividend(date(2026, 6, 1), D("1000.00"), qualified=True)
    ordinary = TaxAccount(TaxRates.of("0.32", "0.15", "0.15"), payment_schedule="none")
    ordinary.dividend(date(2026, 6, 1), D("1000.00"), qualified=False)
    assert qualified.liability(date(2026, 12, 31)) == D("150.00")
    assert ordinary.liability(date(2026, 12, 31)) == D("320.00")


def test_quarterly_estimates_pay_as_the_income_is_earned():
    """1040-ES: a Q1 gain is due 15 April of the same year, not the following one."""
    account = TaxAccount(TaxRates.of("0.32"), payment_schedule="quarterly")
    account.realize(date(2026, 2, 10), D("10000.00"), long_term=False)
    assert account.settle(date(2026, 4, 14)) == D("0.00")
    assert account.settle(date(2026, 4, 15)) == D("3200.00")
    assert account.reserve(date(2026, 4, 15)) == D("0.00")


def test_the_annual_schedule_defers_the_whole_bill_to_april_of_the_next_year():
    account = TaxAccount(TaxRates.of("0.32"), payment_schedule="annual")
    account.realize(date(2026, 2, 10), D("10000.00"), long_term=False)
    assert account.settle(date(2026, 12, 31)) == D("0.00")
    assert account.reserve(date(2026, 12, 31)) == D("3200.00")
    assert account.settle(date(2027, 4, 15)) == D("3200.00")


def test_a_later_loss_does_not_claw_back_a_payment_already_made():
    """Cash paid to the IRS in April is gone for the year; the reserve simply stops growing."""
    account = TaxAccount(TaxRates.of("0.32"), payment_schedule="quarterly")
    account.realize(date(2026, 2, 10), D("10000.00"), long_term=False)
    account.settle(date(2026, 4, 15))
    account.realize(date(2026, 7, 1), D("-10000.00"), long_term=False)
    assert account.reserve(date(2026, 12, 31)) == D("0.00")
    assert sum(account.paid.values()) == D("3200.00")


def test_available_to_withdraw_is_equity_minus_the_reserve():
    ledger = TaxLedger(NO_PAY)
    ledger.buy(date(2026, 1, 5), "AAA", 100, "100")
    ledger.sell(date(2026, 3, 5), "AAA", 100, "150")
    snapshot = ledger.snapshot(D("105000.00"))
    assert snapshot.reserve == D("1600.00")
    assert snapshot.available_to_withdraw == D("103400.00")
