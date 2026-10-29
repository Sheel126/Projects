"""After the lockbox (lesson 04 §7): why the overlay failed. Diagnosis only; the verdict was fixed
by the pre-registration and nothing here can change it.

    python scripts/lockbox_diagnostic.py > ../docs/phase4/lockbox_diagnostic.txt
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import psycopg  # noqa: E402

import run_phase3d as r3d  # noqa: E402
import run_phase4 as r4  # noqa: E402
from liquid_atm_quant.config import get_settings  # noqa: E402
from liquid_atm_quant.intraday.account import run_account  # noqa: E402
from liquid_atm_quant.intraday.noise_band import NoiseBand, NoiseBandParams  # noqa: E402
from liquid_atm_quant.strategy import LOCKBOX_START  # noqa: E402


def main() -> int:
    with psycopg.connect(get_settings().database_url, connect_timeout=5) as conn:
        end = r4.data_end(conn)
        runner = r3d.Runner(conn, start=date(2016, 1, 4), end=end, panel_symbols=r4.ETFS)
        nb = NoiseBand(runner.grid, NoiseBandParams())
        res = run_account(runner.sessions, runner.daily, nb.day, "noise_band")
    eq = res.equity
    pnl = eq["overlay_pnl"].astype(float)
    capital = (eq["equity_after_tax"].astype(float).shift(1)).fillna(100_000.0)
    day_ret = pnl / capital
    spy = np.array([runner.daily[d].close for d in runner.sessions])
    spy_ret = np.concatenate([[np.nan], spy[1:] / spy[:-1] - 1])
    print("Noise Band alone (trial 18's rules), pre-tax daily P&L as % of prior after-tax equity\n")
    print(f"{'period':<22} {'days':>5} {'mean/day':>9} {'ann.':>7} {'hit':>6} "
          f"{'SPY<-1%':>8} {'quiet':>7} {'corr SPY':>9}")
    periods = [(f"{y}", date(y, 1, 1), date(y, 12, 31)) for y in range(2016, end.year + 1)]
    periods += [("in sample 2016-24/09", r3d.START, r3d.END), ("lockbox 2024/10-", LOCKBOX_START, end)]
    for label, a, b in periods:
        mask = np.array([a <= d <= b for d in runner.sessions]) & np.isfinite(spy_ret)
        r, s = day_ret.to_numpy()[mask], spy_ret[mask]
        traded = r != 0
        down, quiet = s < -0.01, np.abs(s) < 0.005
        print(f"{label:<22} {mask.sum():>5} {r.mean():>9.4%} {r.mean() * 252:>7.1%} "
              f"{(r[traded] > 0).mean():>6.1%} {r[down].mean() if down.any() else 0:>8.2%} "
              f"{r[quiet].mean():>7.2%} {np.corrcoef(r, s)[0, 1]:>9.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
