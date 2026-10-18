"""Run every scenario in shared/tax-fixtures/ against the Python tax engine.

    python scripts/tax_fixtures.py            # pass/fail table, exit 1 on any failure
    python scripts/tax_fixtures.py -v         # also dump the resulting ledger state

The Java engine in Phase 6 reads the same files and must produce identical output (lesson 02 §8).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from liquid_atm_quant.tax.fixtures import FIXTURE_DIR, run_all  # noqa: E402


def main() -> int:
    verbose = "-v" in sys.argv
    results = run_all()
    if not results:
        print(f"no fixtures found in {FIXTURE_DIR}")
        return 1

    width = max(len(r.name) for r in results)
    failures = 0
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"  {status}  {result.name:<{width}}  {result.path.name}")
        for mismatch in result.mismatches:
            print(f"          {mismatch}")
        if verbose:
            state = result.state
            print(f"          realized={state.realized_gain} reserve={state.tax_reserve} "
                  f"deferred={state.deferred_loss_balance} carryforward={state.carryforward}")
            for lot in state.open_lots:
                print(f"          open lot {lot}")
        failures += not result.passed

    print(f"\n{len(results) - failures}/{len(results)} fixtures pass")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
