"""Run the baselines and the Phase 3 funnel, and print the comparisons their gates turn on.

    python scripts/run_backtest.py                       # SPY buy-and-hold + naive momentum
    python scripts/run_backtest.py --strategy spy
    python scripts/run_backtest.py --start 2016-01-04 --end 2026-09-26 --save
    python scripts/run_backtest.py --strategy phase3 --save          # the Phase 3 gate (lesson 03 §9)
    python scripts/run_backtest.py --strategy funnel --strict-fills  # touch-only fills rejected
    python scripts/run_backtest.py --strategy funnel --param stop_atr=2.5   # one more trial

Any run that includes the funnel stops before the lockbox (2024-10-01) unless `--unlock-lockbox`
is passed, and prints how many of the 20-trial budget have been used (lesson 03 §1).

The gate: SPY buy-and-hold through this engine must reproduce SPY's actual CAGR and max drawdown
for the window. If it does not, the engine is wrong and nothing downstream means anything
(lesson 02 §9).
"""

import argparse
import json
import logging
import sys
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import psycopg  # noqa: E402

from liquid_atm_quant.backtest import metrics as m  # noqa: E402
from liquid_atm_quant.backtest.engine import BacktestConfig, Backtester  # noqa: E402
from liquid_atm_quant.backtest.panel import Panel  # noqa: E402
from liquid_atm_quant.baselines import BuyAndHold, NaiveMomentum  # noqa: E402
from liquid_atm_quant.config import get_settings  # noqa: E402
from liquid_atm_quant.strategy import (LOCKBOX_START, TRIAL_BUDGET, FunnelParams,  # noqa: E402
                                       LockboxError, MomentumFunnel, assert_outside_lockbox)
from liquid_atm_quant.strategy.sectors import load_sectors  # noqa: E402
from liquid_atm_quant.tax.ledger import TaxConfig  # noqa: E402

log = logging.getLogger("run_backtest")

DEFAULT_START = date(2016, 1, 4)     # Alpaca SIP history begins here (lesson 01 §1)


def build_config(args) -> BacktestConfig:
    return BacktestConfig(
        initial_cash=Decimal(args.cash),
        max_positions=args.top_n,
        entry_buffer=Decimal(args.entry_buffer),
        adv_participation=Decimal(args.adv_participation),
        december_flush=args.december_flush,
        risk_free_rate=Decimal(args.risk_free),
        tax=TaxConfig(short_term_rate=Decimal(args.short_term_rate),
                      long_term_rate=Decimal(args.long_term_rate),
                      payment_schedule=args.payment_schedule))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--end", type=date.fromisoformat, default=None,
                        help="default: today, or the day before the lockbox when the funnel runs")
    parser.add_argument("--strategy", choices=["all", "spy", "momentum", "funnel", "phase3"],
                        default="all", help="all = the two baselines; phase3 = baselines + funnel")
    parser.add_argument("--param", action="append", default=[], metavar="KEY=VALUE",
                        help="override a FunnelParams field (each distinct set is one trial)")
    parser.add_argument("--strict-fills", action="store_true",
                        help="reject touch-only entry fills (lesson 03 §9 sensitivity run)")
    parser.add_argument("--unlock-lockbox", action="store_true",
                        help="allow a funnel run into the holdout; Phase 4's final run only")
    parser.add_argument("--label", default=None, help="label stored with --save")
    parser.add_argument("--benchmark", default="SPY")
    parser.add_argument("--index", default="russell1000",
                        help="point-in-time universe for the momentum baseline")
    parser.add_argument("--cash", default="100000.00")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--entry-buffer", default="0.01")
    parser.add_argument("--adv-participation", default="0.01")
    parser.add_argument("--short-term-rate", default="0.32")
    parser.add_argument("--long-term-rate", default="0.15")
    parser.add_argument("--payment-schedule", choices=["quarterly", "annual", "none"],
                        default="quarterly")
    parser.add_argument("--risk-free", default="0")
    parser.add_argument("--december-flush", action="store_true")
    parser.add_argument("--save", action="store_true", help="store runs in backtest_runs (V5)")
    parser.add_argument("--json", action="store_true", help="emit the full report as JSON")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    with_funnel = args.strategy in ("funnel", "phase3")
    if args.end is None:
        args.end = LOCKBOX_START - timedelta(days=1) if with_funnel else date.today()
    if with_funnel:
        try:
            assert_outside_lockbox(args.end, args.unlock_lockbox)
        except LockboxError as exc:
            print(exc, file=sys.stderr)
            return 3
    params = FunnelParams().with_overrides(dict(kv.split("=", 1) for kv in args.param))

    settings = get_settings()
    try:
        conn = psycopg.connect(settings.database_url, connect_timeout=5)
    except psycopg.Error as exc:
        print(f"database not reachable ({exc})\n"
              "run `docker compose up -d postgres orchestrator` first", file=sys.stderr)
        return 2

    config = build_config(args)
    with conn:
        log.info("loading panel %s..%s", args.start, args.end)
        panel = Panel.from_db(conn, args.start, args.end, index_name=args.index)
        log.info("panel: %d sessions x %d symbols", *panel.shape)

        runs = []
        if args.strategy in ("all", "spy", "phase3"):
            runs.append(Backtester(panel, config).run(BuyAndHold(args.benchmark)))
        if args.strategy in ("all", "momentum", "phase3"):
            runs.append(Backtester(panel, config).run(NaiveMomentum(top_n=args.top_n)))
        if with_funnel:
            funnel_config = replace(config, max_positions=params.max_positions,
                                    strict_fills=args.strict_fills)
            funnel = MomentumFunnel(params, sectors=load_sectors(conn))
            runs.append(Backtester(panel, funnel_config).run(funnel))

        reports = [m.report(r) for r in runs]
        if args.save:
            from liquid_atm_quant.backtest import store
            label = args.label or ("phase3" if with_funnel else "phase2_baseline")
            for run in runs:
                log.info("saved run %d (%s)", store.save(conn, run, label=label), run.strategy)
            conn.commit()
        trials = store_trials(conn) if with_funnel else None

    if args.json:
        print(json.dumps(reports, indent=2, default=str))
        return 0

    for run, rep in zip(runs, reports, strict=True):
        print(f"\n=== {run.strategy}  [{run.config_hash}] "
              f"{rep['pre_tax']['start']} .. {rep['pre_tax']['end']}")
        print(f"  pre-tax    {m.compute(run.equity['equity'], float(config.risk_free_rate)).summary()}")
        print(f"  after-tax  "
              f"{m.compute(run.equity['equity_after_tax'], float(config.risk_free_rate)).summary()}")
        print(f"  post-liquidation value  {run.post_liquidation_value:>14,}   "
              f"(tax paid {rep['tax']['tax_paid']:,.2f} + terminal {rep['tax']['terminal_tax']:,.2f})")
        trades, diag, tax = rep["trades"], rep["diagnostics"], rep["tax"]
        print(f"  trades {trades['n_trades']:>5}   hit {trades['hit_rate']:.1%}   "
              f"avg hold {trades['avg_days_held']:.1f}d   exits {trades['exit_reasons']}")
        print(f"  fills: rate {diag['fill_rate']:.1%}  touch-only {diag['touch_fill_rate']:.1%}  "
              f"ambiguous exits {diag['ambiguity_rate']:.1%}  adv-capped {diag['adv_capped']}")
        print(f"  tax: effective {tax['effective_tax_rate']:.1%}   "
              f"wash sales {diag['wash_sales']}   deferred loss {tax['deferred_loss_balance']:,.2f}")
        if "strategy" in diag:
            funnel_diag = diag["strategy"]
            print(f"  R: expectancy {trades['expectancy_r']:+.3f}R   avg win "
                  f"{trades['avg_win_r']:+.2f}R   avg loss {trades['avg_loss_r']:+.2f}R   "
                  f"expired entries {diag['entries_expired']}   strict-rejected "
                  f"{diag['strict_rejected']}")
            print(f"  regime days {funnel_diag['regime_days']}")
            print(f"  funnel/day {funnel_diag['avg_per_stage']}   book skips "
                  f"{funnel_diag['book_skips']}")

    if with_funnel and len(runs) == 3:
        print_gate(runs, reports)
    if trials is not None:
        print(f"\n  trials used: {trials}/{TRIAL_BUDGET} distinct funnel configurations saved"
              + ("" if args.save else " (this run was not saved; pass --save to count it)"))
    if len(runs) == 2:
        print(f"\n  after-tax post-liquidation: {runs[1].strategy} "
              f"{runs[1].post_liquidation_value:,} vs {runs[0].strategy} "
              f"{runs[0].post_liquidation_value:,}")
    return 0


def store_trials(conn) -> int:
    from liquid_atm_quant.backtest import store
    return store.trial_count(conn, MomentumFunnel.name)


def print_gate(runs, reports) -> bool:
    """The Phase 3 in-sample gate (lesson 03 §9). Criterion 4, strict fills, is a separate run."""
    spy, momentum, funnel = runs
    rep_spy, rep_funnel = reports[0], reports[2]
    dd = rep_funnel["after_tax"]["max_drawdown"]
    checks = [
        ("post-liquidation value beats SPY buy & hold",
         funnel.post_liquidation_value > spy.post_liquidation_value,
         f"{funnel.post_liquidation_value:,} vs {spy.post_liquidation_value:,}"),
        ("post-liquidation value beats naive momentum",
         funnel.post_liquidation_value > momentum.post_liquidation_value,
         f"{funnel.post_liquidation_value:,} vs {momentum.post_liquidation_value:,}"),
        ("max drawdown (after tax) <= 20%", dd >= -0.20, f"{dd:.2%}"),
        ("Calmar (after tax) beats SPY's",
         rep_funnel["after_tax"]["calmar"] > rep_spy["after_tax"]["calmar"],
         f"{rep_funnel['after_tax']['calmar']:.2f} vs {rep_spy['after_tax']['calmar']:.2f}"),
    ]
    print("\n=== Phase 3 in-sample gate")
    for name, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<46} {detail}")
    print("  ....  result survives strict fills              rerun with --strict-fills")
    return all(ok for _, ok, _ in checks)


if __name__ == "__main__":
    sys.exit(main())
