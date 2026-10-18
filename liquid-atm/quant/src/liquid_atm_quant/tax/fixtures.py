"""Runner for `shared/tax-fixtures/` (lesson 02 §8).

A fixture is a JSON scenario plus the exact ledger it must produce. The Java engine in Phase 6
reads the same files, so anything asserted here is a contract between the two engines, not a
Python unit test. Only the keys present in `expected` are compared, which lets a fixture pin one
behaviour without restating the whole ledger.
"""

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from liquid_atm_quant.tax.ledger import LedgerState, TaxConfig, TaxLedger
from liquid_atm_quant.tax.money import cents, money

FIXTURE_DIR = Path(__file__).resolve().parents[3].parent / "shared" / "tax-fixtures"


@dataclass
class FixtureResult:
    name: str
    path: Path
    passed: bool
    mismatches: list[str]
    state: LedgerState

    def report(self) -> str:
        head = f"{'PASS' if self.passed else 'FAIL'}  {self.name}"
        return head if self.passed else head + "\n" + "\n".join(f"    {m}" for m in self.mismatches)


def load_fixtures(directory: Path | None = None) -> list[dict]:
    directory = directory or FIXTURE_DIR
    out = []
    for path in sorted(directory.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["_path"] = path
        out.append(raw)
    return out


def run_fixture(fixture: dict) -> FixtureResult:
    ledger = TaxLedger(TaxConfig.from_dict(fixture.get("config", {})))
    for event in fixture["trades"]:
        when = date.fromisoformat(event["date"])
        side = event["side"]
        if side == "buy":
            ledger.buy(when, event["symbol"], money(event["qty"]), money(event["price"]),
                       money(event.get("fees", 0)))
        elif side == "sell":
            ledger.sell(when, event["symbol"], money(event["qty"]), money(event["price"]),
                        money(event.get("fees", 0)), event.get("exit_reason"))
        elif side == "dividend":
            ledger.dividend(when, money(event["amount"]))
        elif side == "settle":
            ledger.settle(when)
        else:
            raise ValueError(f"unknown side {side!r} in {fixture['name']}")

    as_of = date.fromisoformat(fixture["as_of"]) if "as_of" in fixture else None
    if as_of is not None:
        ledger.settle(as_of)
    state = ledger.state(as_of)
    mismatches = _compare(fixture["expected"], state)
    return FixtureResult(fixture["name"], fixture.get("_path", Path(".")), not mismatches,
                         mismatches, state)


def run_all(directory: Path | None = None) -> list[FixtureResult]:
    return [run_fixture(f) for f in load_fixtures(directory)]


# ---- comparison ----------------------------------------------------------------------------

_SCALARS = ("realized_gain", "tax_reserve", "carryforward", "deferred_loss_balance")
_LIST_KEYS = {
    "disallowed_losses": ("sell_date", "symbol", "amount"),
    "open_lots": ("symbol", "qty", "cost_basis", "acquired", "holding_period_start"),
    "blacklist": ("symbol", "until"),
}


def _compare(expected: dict, state: LedgerState) -> list[str]:
    out: list[str] = []
    for key in _SCALARS:
        if key in expected:
            want, got = cents(expected[key]), cents(getattr(state, key))
            if want != got:
                out.append(f"{key}: expected {want}, got {got}")
    for key, fields in _LIST_KEYS.items():
        if key not in expected:
            continue
        want_rows = [_normalise(row, fields) for row in expected[key]]
        got_rows = [_normalise(row, fields) for row in getattr(state, key)]
        if len(want_rows) != len(got_rows):
            out.append(f"{key}: expected {len(want_rows)} row(s), got {len(got_rows)}: {got_rows}")
            continue
        for i, (want, got) in enumerate(zip(want_rows, got_rows, strict=True)):
            if want != got:
                out.append(f"{key}[{i}]: expected {want}, got {got}")
    return out


def _normalise(row: dict, fields: tuple[str, ...]) -> dict:
    """Compare only the fields a fixture declares, with numbers coerced to exact decimals."""
    out = {}
    for name in fields:
        if name not in row:
            continue
        value = row[name]
        out[name] = _quantize(name, value) if isinstance(value, (int, float, Decimal)) else value
    return out


def _quantize(name: str, value: object) -> Decimal:
    # Share counts keep their own precision; everything else is money, so cents.
    return money(value).normalize() if name == "qty" else cents(value)
