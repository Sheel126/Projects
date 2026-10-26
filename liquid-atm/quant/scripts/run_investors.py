"""Run the Phase 3b investor strategies against the baselines and apply the in-sample gate.

    python scripts/run_investors.py                    # all eight + SPY + naive momentum
    python scripts/run_investors.py --only buffett_quality,all_weather
    python scripts/run_investors.py --save             # store the runs: each is a trial
    python scripts/run_investors.py --json docs/phase3b/results.json

Everything stops the day before the lockbox (2024-10-01); there is no flag to go past it here.
The gate is lesson 03 §9's, unchanged (lesson 03b §5): after-tax post-liquidation value beats SPY
buy-and-hold and naive momentum, after-tax max drawdown within 20%, after-tax Calmar above SPY's.
"""

import argparse
import json
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import psycopg  # noqa: E402

from liquid_atm_quant.backtest import metrics as m  # noqa: E402
from liquid_atm_quant.backtest import store  # noqa: E402
from liquid_atm_quant.backtest.engine import BacktestConfig, Backtester  # noqa: E402
from liquid_atm_quant.backtest.fundamentals import Fundamentals  # noqa: E402
from liquid_atm_quant.backtest.panel import Panel  # noqa: E402
from liquid_atm_quant.baselines import BuyAndHold, NaiveMomentum  # noqa: E402
from liquid_atm_quant.config import get_settings  # noqa: E402
from liquid_atm_quant.investors import PHASE3_STRATEGIES, STRATEGIES, build  # noqa: E402
from liquid_atm_quant.strategy import LOCKBOX_START, TRIAL_BUDGET  # noqa: E402
from liquid_atm_quant.strategy.sectors import load_sectors  # noqa: E402

log = logging.getLogger("run_investors")

START = date(2016, 1, 4)
END = LOCKBOX_START - timedelta(days=1)
WARMUP = timedelta(days=450)
"""Calendar days of history loaded before START (ETF bars go back to 2005) so a 200-day rule has
its average on day one. Nothing trades or is scored before START."""


def gate(rep: dict, spy: dict, momentum: dict) -> list[tuple[str, bool, str]]:
    value, dd = rep["post_liquidation_value"], rep["after_tax"]["max_drawdown"]
    return [
        ("beats SPY after tax", value > spy["post_liquidation_value"],
         f"{value:,.0f} vs {spy['post_liquidation_value']:,.0f}"),
        ("beats naive momentum after tax", value > momentum["post_liquidation_value"],
         f"{value:,.0f} vs {momentum['post_liquidation_value']:,.0f}"),
        ("max drawdown <= 20%", dd >= -0.20, f"{dd:.1%}"),
        ("Calmar beats SPY's", rep["after_tax"]["calmar"] > spy["after_tax"]["calmar"],
         f"{rep['after_tax']['calmar']:.2f} vs {spy['after_tax']['calmar']:.2f}"),
    ]


def trials_used(conn: psycopg.Connection) -> int:
    return sum(store.trial_count(conn, name) for name in (*PHASE3_STRATEGIES, *STRATEGIES))


def long_term_share(result) -> float:
    gains = [float(t.realized_gain) for t in result.trades if t.realized_gain > 0]
    long_gains = [float(t.realized_gain) for t in result.trades
                  if t.realized_gain > 0 and t.is_long_term]
    return sum(long_gains) / sum(gains) if gains else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="comma-separated subset of: " + ", ".join(STRATEGIES))
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--label", default="phase3b")
    parser.add_argument("--json", type=Path, help="write every report to this file")
    parser.add_argument("--index", default="russell1000")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    names = args.only.split(",") if args.only else list(STRATEGIES)
    unknown = set(names) - set(STRATEGIES)
    if unknown:
        parser.error(f"unknown strategies: {sorted(unknown)}")

    conn = psycopg.connect(get_settings().database_url, connect_timeout=5)
    config = BacktestConfig()
    with conn:
        t0 = time.time()
        panel = Panel.from_db(conn, START - WARMUP, END, index_name=args.index)
        fundamentals = Fundamentals.from_db(conn, panel)
        sectors = load_sectors(conn)
        log.info("panel %d x %d, fundamentals for %d symbols (%.0fs)", *panel.shape,
                 len(fundamentals.symbols), time.time() - t0)

        results = {}
        for strategy in (BuyAndHold("SPY"), NaiveMomentum()):
            results[strategy.name] = Backtester(panel, config).run(strategy, START)
        for name in names:
            t0 = time.time()
            results[name] = Backtester(panel, config).run(build(name, fundamentals, sectors),
                                                           START)
            log.info("%s done in %.0fs", name, time.time() - t0)

        reports = {name: m.report(r) for name, r in results.items()}
        if args.save:
            for name in names:
                run_id = store.save(conn, results[name], label=args.label)
                log.info("saved run %d (%s)", run_id, name)
            conn.commit()
        used = trials_used(conn)

    spy, momentum = reports["buy_and_hold_spy"], reports["naive_momentum"]
    header = (f"{'strategy':<18} {'after-tax value':>15} {'CAGR':>7} {'maxDD':>7} {'Calmar':>7} "
              f"{'Sharpe':>7} {'trades':>7} {'hold d':>7} {'tax':>6} {'LT gain':>8}  gate")
    print("\n" + header + "\n" + "-" * len(header))
    for name, rep in reports.items():
        at, tr = rep["after_tax"], rep["trades"]
        checks = gate(rep, spy, momentum) if name in STRATEGIES else []
        verdict = ("PASS" if all(ok for _, ok, _ in checks) else
                   f"fail {sum(not ok for _, ok, _ in checks)}/4") if checks else "(baseline)"
        print(f"{name:<18} {rep['post_liquidation_value']:>15,.0f} {at['cagr']:>7.2%} "
              f"{at['max_drawdown']:>7.1%} {at['calmar']:>7.2f} {at['sharpe']:>7.2f} "
              f"{tr['n_trades']:>7} {tr['avg_days_held']:>7.0f} "
              f"{rep['tax']['effective_tax_rate']:>6.1%} {long_term_share(results[name]):>8.0%}  "
              f"{verdict}")
    for name in names:
        print(f"\n=== {name}  [{reports[name]['config_hash']}]")
        for label, ok, detail in gate(reports[name], spy, momentum):
            print(f"  {'PASS' if ok else 'FAIL'}  {label:<32} {detail}")
        print(f"  diagnostics: {reports[name]['diagnostics'].get('strategy')}")
    print(f"\ntrials used: {used}/{TRIAL_BUDGET}"
          + ("" if args.save else " (not saved; pass --save to count these runs)"))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {name: {**rep, "long_term_gain_share": long_term_share(results[name]),
                          "equity_after_tax": {str(d): float(v) for d, v in
                                               results[name].equity["equity_after_tax"].items()}}
                   for name, rep in reports.items()}
        args.json.write_text(json.dumps(store._finite(payload), indent=1, default=str))
        log.info("wrote %s", args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
