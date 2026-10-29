"""Robustness checks on the two Noise Band trials (lesson 03d §4). Not trials: nothing here is
adopted, and nothing is saved. It answers "how fragile is the in-sample number?"

    python scripts/noise_sensitivity.py
"""

import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

import run_phase3d as r  # noqa: E402
from liquid_atm_quant.config import get_settings  # noqa: E402
from liquid_atm_quant.intraday.account import run_account  # noqa: E402
from liquid_atm_quant.intraday.noise_band import NoiseBand, NoiseBandParams  # noqa: E402


def main() -> int:
    with psycopg.connect(get_settings().database_url, connect_timeout=5) as conn:
        runner = r.Runner(conn)
    grid = runner.grid
    base = NoiseBandParams()
    variants = {
        "as registered": base,
        "costs x2": replace(base, commission_per_share=0.007, slippage_per_share=0.002),
        "costs x4": replace(base, commission_per_share=0.014, slippage_per_share=0.004),
        "Alpaca costs ($0 commission)": replace(base, commission_per_share=0.0),
        "vm 1.5 (paper's hindsight best)": replace(base, vm=1.5),
        "max leverage 2": replace(base, max_leverage=2.0),
    }
    periods = {"2016-2019": (date(2016, 1, 4), date(2019, 12, 31)),
               "2020-2024": (date(2020, 1, 2), date(2024, 9, 30))}
    print(f"{'variant':<34} {'core':>5} {'after-tax value':>15} {'CAGR':>7} {'maxDD':>7} "
          f"{'Calmar':>7}")
    for core in (False, True):
        for label, params in variants.items():
            if core:
                params = replace(params, max_leverage=min(params.max_leverage,
                                                          r.OVERLAY_MAX_LEVERAGE))
            nb = NoiseBand(grid, params)
            rep = run_account(runner.sessions, runner.daily, nb.day, "x", core=core).report()
            at = rep["after_tax"]
            print(f"{label:<34} {str(core):>5} {rep['post_liquidation_value']:>15,.0f} "
                  f"{at['cagr']:>7.2%} {at['max_drawdown']:>7.1%} {at['calmar']:>7.2f}")
        for label, (a, b) in periods.items():
            days = [d for d in runner.sessions if a <= d <= b]
            params = replace(base, max_leverage=r.OVERLAY_MAX_LEVERAGE) if core else base
            for name, fn in (("strategy", NoiseBand(grid, params).day), ("SPY only", None)):
                if fn is None and not core:
                    continue
                rep = run_account(days, runner.daily, fn, "x", core=core).report()
                at = rep["after_tax"]
                print(f"{label + ' ' + name:<34} {str(core):>5} "
                      f"{rep['post_liquidation_value']:>15,.0f} {at['cagr']:>7.2%} "
                      f"{at['max_drawdown']:>7.1%} {at['calmar']:>7.2f}")
    print(f"\n{'vol_trend core + overlay':<34} {'after-tax value':>15} {'CAGR':>7} {'maxDD':>7} "
          f"{'Calmar':>7}")
    with psycopg.connect(get_settings().database_url, connect_timeout=5) as conn:
        runner.conn = conn
        for label, params in variants.items():
            params = replace(params, max_leverage=min(params.max_leverage,
                                                      r.VOL_TREND_OVERLAY_MAX_LEVERAGE))
            rep = runner.vol_trend_noise(params)
            at = rep["after_tax"]
            print(f"{label:<34} {rep['post_liquidation_value']:>15,.0f} {at['cagr']:>7.2%} "
                  f"{at['max_drawdown']:>7.1%} {at['calmar']:>7.2f}")
        later = [d for d in runner.sessions if d >= date(2020, 1, 2)]
        rep = runner.vol_trend_noise(None, later)
        at = rep["after_tax"]
        print(f"{'2020-2024 only':<34} {rep['post_liquidation_value']:>15,.0f} {at['cagr']:>7.2%} "
              f"{at['max_drawdown']:>7.1%} {at['calmar']:>7.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
