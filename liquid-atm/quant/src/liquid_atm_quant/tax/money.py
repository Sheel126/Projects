"""Exact decimal money (lesson 02 §5).

Every amount in the tax engine is a `Decimal` quantized to cents with ROUND_HALF_UP, which is
what Java's `RoundingMode.HALF_UP` does, so the Phase 6 ledger can agree to the penny.
Share quantities keep more precision (Alpaca supports fractional shares) but are still Decimal:
a float qty times a Decimal price is a TypeError, and that is the point.
"""

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
QTY = Decimal("0.000001")       # 6 dp, matches NUMERIC(14,4) headroom for fractional shares
ZERO = Decimal("0.00")


def money(value: object) -> Decimal:
    """Coerce to Decimal without going through binary float when avoidable."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        # repr() of a float is the shortest string that round-trips, so this is the intended value.
        # float() first because numpy scalars subclass float but repr as "np.float64(99.5)".
        return Decimal(repr(float(value)))
    if isinstance(value, int):
        return Decimal(value)
    return Decimal(str(value))


def cents(value: object) -> Decimal:
    """Round to cents, half away from zero (matches Java HALF_UP)."""
    return money(value).quantize(CENT, rounding=ROUND_HALF_UP)


def qty(value: object) -> Decimal:
    return money(value).quantize(QTY, rounding=ROUND_HALF_UP)


def allocate(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split `total` across `weights` in cents with no leaked pennies.

    The residual from rounding lands on the last non-zero slice, so `sum(result) == total`
    exactly. Used for spreading a sell fill's fees across the lots it consumed.
    """
    total = cents(total)
    denominator = sum(weights)
    if denominator == 0:
        return [ZERO for _ in weights]
    out = [cents(total * w / denominator) for w in weights]
    residual = total - sum(out)
    if residual != 0:
        for i in range(len(out) - 1, -1, -1):
            if weights[i] != 0:
                out[i] += residual
                break
    return out
