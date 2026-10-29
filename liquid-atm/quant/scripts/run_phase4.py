"""Phase 4: validate `vol_trend_noise` against its pre-registration (lesson 04).

    python scripts/run_phase4.py fetch                     # daily ETFs + SPY minutes to today
    python scripts/run_phase4.py insample                  # check 1 + the reported statistics
    python scripts/run_phase4.py lockbox --unlock-lockbox  # checks 2-4. ONCE.

The rules are in docs/phase4/preregistration.md, committed before anything here ran. `fetch`
downloads lockbox data but reads none of it. `insample` stops on 2024-09-30. `lockbox` refuses to
run unless the pre-registration is committed and unchanged, and writes
docs/phase4/lockbox_opened.json before it computes anything, so it cannot be run twice.
"""

import argparse
import json
import logging
import math
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import psycopg  # noqa: E402

import run_phase3d as r3d  # noqa: E402
from liquid_atm_quant.backtest import metrics as m  # noqa: E402
from liquid_atm_quant.backtest import store  # noqa: E402
from liquid_atm_quant.backtest.engine import BacktestConfig, Backtester  # noqa: E402
from liquid_atm_quant.baselines import BuyAndHold  # noqa: E402
from liquid_atm_quant.config import get_settings  # noqa: E402
from liquid_atm_quant.data import db  # noqa: E402
from liquid_atm_quant.data.alpaca_data import AlpacaData  # noqa: E402
from liquid_atm_quant.data.coverage import ALPACA_HISTORY_START  # noqa: E402
from liquid_atm_quant.infra.rate_limiter import alpaca_limiter  # noqa: E402
from liquid_atm_quant.infra.redis_client import make_redis  # noqa: E402
from liquid_atm_quant.intraday import bars  # noqa: E402
from liquid_atm_quant.intraday.account import calendar_returns  # noqa: E402
from liquid_atm_quant.strategy import LOCKBOX_START  # noqa: E402
from liquid_atm_quant.validation import (check_preregistration, cscv_pbo,  # noqa: E402
                                         deflated_sharpe, open_once, sharpe,
                                         stationary_bootstrap)

log = logging.getLogger("run_phase4")

DOCS = Path(__file__).resolve().parents[2] / "docs" / "phase4"
PREREGISTRATION = DOCS / "preregistration.md"
MARKER = DOCS / "lockbox_opened.json"
RERUNS = DOCS.parent / "phase3d" / "rerun_phase3b3c.json"
CANDIDATE = "vol_trend_noise"
CANDIDATE_HASH = "025b6455f4fec66e"
N_TRIALS = 24
ETFS = ["SPY", "SSO", "BIL"]
DSR_MIN = 0.95
LOCKBOX_MAX_DD = -0.15


# ---- fetch -------------------------------------------------------------------------------

def fetch(conn: psycopg.Connection) -> None:
    """Re-download the three ETFs' whole Alpaca history (so `adj_factor` shares one base and the
    dividends reconstructed from it have no seam), and SPY minutes from 2024 to the last session."""
    check_preregistration(PREREGISTRATION)
    settings = get_settings()
    client = AlpacaData(settings.alpaca_api_key, settings.alpaca_secret_key,
                        alpaca_limiter(make_redis(settings)))
    db.upsert_calendar(conn, client.calendar(date.today() - timedelta(days=60),
                                             date.today() + timedelta(days=30)))
    conn.commit()
    last = db.last_completed_session(conn, datetime.now(UTC))
    rows = client.daily_bars(ETFS, ALPACA_HISTORY_START, last)
    log.info("daily bars %s..%s: %d rows", ALPACA_HISTORY_START, last, db.upsert_bars(conn, rows))
    conn.commit()
    for year in range(LOCKBOX_START.year, last.year + 1):
        bars.download_year(client, "SPY", year, through=last)
    log.info("SPY minutes through %s", last)


def data_end(conn: psycopg.Connection) -> date:
    """The last session with both a daily bar for all three ETFs and SPY minutes."""
    with conn.cursor() as cur:
        cur.execute("SELECT min(d) FROM (SELECT max(trade_date) AS d FROM tradable_bars "
                    "WHERE symbol = ANY(%s) GROUP BY symbol) x", (ETFS,))
        daily = cur.fetchone()[0]
    minutes = bars.load("SPY", date(daily.year, 1, 1), daily)
    return min(daily, max(minutes.index.date))


# ---- in sample ---------------------------------------------------------------------------

def trial_curves(conn: psycopg.Connection) -> dict[str, pd.Series]:
    """Every budgeted trial's daily after-tax equity, 2016-01-04 .. 2024-09-30.

    Phases 3b and 3c come from their re-runs on the fixed engine; the funnel's two configurations
    and Phase 3d's seven from the saved runs."""
    curves: dict[str, pd.Series] = {}
    reruns = json.loads(RERUNS.read_text())
    for name, rep in reruns.items():
        if name in ("buy_and_hold_spy", "naive_momentum"):
            continue
        curves[name] = _series(rep["equity_after_tax"])
    with conn.cursor() as cur:
        cur.execute("""SELECT DISTINCT ON (strategy, config_hash) id, strategy, config_hash
                       FROM backtest_runs
                       WHERE strategy = ANY(%s) AND end_date = %s
                       ORDER BY strategy, config_hash, id DESC""",
                    (["momentum_funnel", *r3d.PHASE3D_STRATEGIES], r3d.END))
        runs = cur.fetchall()
        for run_id, name, config_hash in runs:
            cur.execute("SELECT trade_date, equity_after_tax FROM backtest_equity "
                        "WHERE run_id = %s ORDER BY trade_date", (run_id,))
            key = name if name != "momentum_funnel" else f"momentum_funnel_{config_hash[:6]}"
            curves[key] = pd.Series({d: float(v) for d, v in cur.fetchall()})
    return curves


def _series(points: dict) -> pd.Series:
    s = pd.Series({date.fromisoformat(k): float(v) for k, v in points.items()})
    return s.sort_index()


def returns_matrix(curves: dict[str, pd.Series]) -> pd.DataFrame:
    frame = pd.DataFrame(curves).sort_index().dropna()
    rets = frame.pct_change().iloc[1:]
    # An account that is wiped out (ORB ends at $84) has meaningless late returns, but they are
    # still that trial's returns; only exact zeros-over-zeros are cleaned.
    return rets.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def insample(conn: psycopg.Connection) -> dict:
    used = r3d.trials_used(conn)
    if used != N_TRIALS:
        raise SystemExit(f"{used} trials saved, the pre-registration says {N_TRIALS}: stop")

    runner = r3d.Runner(conn)
    fresh = runner.vol_trend_noise()
    saved = _saved_value(conn)
    if abs(fresh["post_liquidation_value"] - saved) > 1.0:
        raise SystemExit(f"{CANDIDATE} does not reproduce: {fresh['post_liquidation_value']:,.2f} "
                         f"vs {saved:,.2f} saved")
    etf_runner = r3d.Runner(conn, panel_symbols=ETFS)
    etf = etf_runner.vol_trend_noise()
    if abs(etf["post_liquidation_value"] - saved) > 1.0:
        raise SystemExit("the ETF-only panel does not reproduce the Russell 1000 panel's run: "
                         f"{etf['post_liquidation_value']:,.2f} vs {saved:,.2f}")

    curves = trial_curves(conn)
    if len(curves) != N_TRIALS:
        raise SystemExit(f"found {len(curves)} trial curves, expected {N_TRIALS}: {sorted(curves)}")
    curves[CANDIDATE] = fresh["_equity"]["equity_after_tax"].astype(float)
    rets = returns_matrix(curves)
    trial_sr = np.array([sharpe(rets[c].to_numpy()) for c in rets.columns])
    dsr = deflated_sharpe(rets[CANDIDATE].to_numpy(), trial_sr, N_TRIALS)
    pbo = cscv_pbo(rets.to_numpy(), list(rets.columns), blocks=16)

    reruns = json.loads(RERUNS.read_text())
    spy = _series(reruns["buy_and_hold_spy"]["equity_after_tax"])
    vol_trend = _series(reruns["vol_trend"]["equity_after_tax"])
    both = pd.DataFrame({"c": curves[CANDIDATE], "spy": spy}).dropna().pct_change().iloc[1:]
    boot = stationary_bootstrap((both["c"] - both["spy"]).to_numpy())

    years = {"vol_trend_noise": calendar_returns(curves[CANDIDATE]),
             "vol_trend": calendar_returns(vol_trend), "spy": calendar_returns(spy)}
    return {
        "check_1_dsr": {"pass": dsr.dsr >= DSR_MIN, "threshold": DSR_MIN, **dsr.as_dict()},
        "trial_sharpes_annual": {c: round(s * math.sqrt(252), 3)
                                 for c, s in sorted(zip(rets.columns, trial_sr),
                                                    key=lambda kv: -kv[1])},
        "pbo": pbo.as_dict(),
        "bootstrap_vs_spy": boot,
        "calendar_after_tax": years,
        "reproduced_post_liquidation_value": fresh["post_liquidation_value"],
        "sessions": len(rets) + 1,
    }


def _saved_value(conn: psycopg.Connection) -> float:
    with conn.cursor() as cur:
        cur.execute("SELECT post_liquidation_value FROM backtest_runs "
                    "WHERE strategy = %s AND config_hash = %s ORDER BY id DESC LIMIT 1",
                    (CANDIDATE, CANDIDATE_HASH))
        return float(cur.fetchone()[0])


def print_insample(out: dict) -> None:
    d = out["check_1_dsr"]
    print(f"\n=== Check 1: Deflated Sharpe ({out['sessions']} sessions, {d['n_trials']} trials)")
    print(f"  candidate Sharpe {d['sharpe_annual']:.2f}/yr (daily {d['sharpe']:.4f}), "
          f"skew {d['skew']:.2f}, kurtosis {d['kurtosis']:.1f}")
    print(f"  best Sharpe expected from {d['n_trials']} skill-less trials: "
          f"{d['expected_max_sharpe_annual']:.2f}/yr")
    print(f"  DSR {d['dsr']:.4f} (needs >= {d['threshold']})  -> "
          f"{'PASS' if d['pass'] else 'FAIL'}")
    print("\n  trial Sharpes (after tax, annualized):")
    for name, s in out["trial_sharpes_annual"].items():
        print(f"    {name:<28} {s:6.2f}")
    p = out["pbo"]
    print(f"\n=== PBO (CSCV, {p['n_splits']} splits): {p['pbo']:.1%}, median logit "
          f"{p['median_logit']:.2f}")
    print(f"  in-sample winners: {p['in_sample_winners']}")
    b = out["bootstrap_vs_spy"]
    print(f"\n=== Bootstrap, candidate minus SPY: {b['annual_mean']:+.2%}/yr, "
          f"P(>0) = {b['p_positive']:.1%}, 90% interval {b['ci90'][0]:+.1%} .. {b['ci90'][1]:+.1%}")
    print("\n=== Calendar years, after tax")
    years = out["calendar_after_tax"]
    print(f"  {'year':<6}" + "".join(f"{k:>17}" for k in years))
    for y in years["spy"]:
        print(f"  {y:<6}" + "".join(f"{years[k].get(y, float('nan')):>17.1%}" for k in years))


# ---- lockbox -----------------------------------------------------------------------------

def lockbox(conn: psycopg.Connection) -> dict:
    end = data_end(conn)
    record = open_once(MARKER, PREREGISTRATION, {"window": [str(LOCKBOX_START), str(end)],
                                                 "candidate": CANDIDATE,
                                                 "config_hash": CANDIDATE_HASH})
    log.info("lockbox opened: %s", record)

    runner = r3d.Runner(conn, start=LOCKBOX_START, end=end, panel_symbols=ETFS)
    combined = runner.vol_trend_noise()
    core = m.report(runner._vol_trend[1])
    spy = m.report(Backtester(runner.panel, BacktestConfig()).run(BuyAndHold("SPY"), LOCKBOX_START))

    value, dd = combined["post_liquidation_value"], combined["after_tax"]["max_drawdown"]
    checks = {
        "check_2_beats_spy": {"pass": value > spy["post_liquidation_value"],
                              "value": value, "spy": spy["post_liquidation_value"]},
        "check_3_drawdown": {"pass": dd >= LOCKBOX_MAX_DD, "max_drawdown": dd,
                             "threshold": LOCKBOX_MAX_DD},
        "check_4_overlay_adds": {"pass": value > core["post_liquidation_value"], "value": value,
                                 "vol_trend_alone": core["post_liquidation_value"]},
    }

    full = r3d.Runner(conn, start=r3d.START, end=end, panel_symbols=ETFS)
    continuous = full.vol_trend_noise()
    spy_full = m.report(Backtester(full.panel, BacktestConfig()).run(BuyAndHold("SPY"), r3d.START))

    def brief(rep: dict) -> dict:
        at = rep["after_tax"]
        return {"post_liquidation_value": rep["post_liquidation_value"], "cagr": at["cagr"],
                "max_drawdown": at["max_drawdown"], "calmar": at["calmar"],
                "sharpe": at["sharpe"], "tax_paid": rep["tax"]["tax_paid"]}

    return {
        "opened": record,
        "window": [str(runner.sessions[0]), str(runner.sessions[-1])],
        "sessions": len(runner.sessions),
        **checks,
        "lockbox": {"vol_trend_noise": brief(combined), "vol_trend": brief(core),
                    "spy": brief(spy)},
        "overlay": {k: combined["diagnostics"].get(k) for k in ("margin_interest",)}
        | {"strategy": combined["diagnostics"].get("strategy")},
        "calendar_after_tax": {
            "vol_trend_noise": calendar_returns(combined["_equity"]["equity_after_tax"]),
            "vol_trend": calendar_returns(runner._vol_trend[1].equity["equity_after_tax"]),
            "spy": calendar_returns(Backtester(runner.panel, BacktestConfig()).run(
                BuyAndHold("SPY"), LOCKBOX_START).equity["equity_after_tax"])},
        "continuous_2016": {"vol_trend_noise": brief(continuous), "spy": brief(spy_full)},
        "equity_after_tax": {str(d): float(v) for d, v in
                             combined["_equity"]["equity_after_tax"].items()},
    }


def print_lockbox(out: dict) -> None:
    print(f"\n=== Lockbox {out['window'][0]} .. {out['window'][1]} ({out['sessions']} sessions)")
    for name, rep in out["lockbox"].items():
        print(f"  {name:<16} {rep['post_liquidation_value']:>12,.0f}  CAGR {rep['cagr']:7.2%}  "
              f"maxDD {rep['max_drawdown']:7.1%}  Calmar {rep['calmar']:5.2f}  "
              f"Sharpe {rep['sharpe']:5.2f}  tax {rep['tax_paid']:>9,.0f}")
    for key in ("check_2_beats_spy", "check_3_drawdown", "check_4_overlay_adds"):
        c = out[key]
        detail = {k: v for k, v in c.items() if k != "pass"}
        print(f"  {'PASS' if c['pass'] else 'FAIL'}  {key:<24} {json.dumps(detail, default=str)}")
    years = out["calendar_after_tax"]
    for y in years["spy"]:
        print(f"  {y}: " + "  ".join(f"{k} {years[k].get(y, float('nan')):+.1%}" for k in years))
    c = out["continuous_2016"]
    print(f"\n  continuous 2016 .. end: vol_trend_noise "
          f"{c['vol_trend_noise']['post_liquidation_value']:,.0f} "
          f"(DD {c['vol_trend_noise']['max_drawdown']:.1%}) vs SPY "
          f"{c['spy']['post_liquidation_value']:,.0f} (DD {c['spy']['max_drawdown']:.1%})")


# ---- entrypoint --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["fetch", "insample", "lockbox"])
    parser.add_argument("--unlock-lockbox", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with psycopg.connect(get_settings().database_url, connect_timeout=5) as conn:
        if args.step == "fetch":
            fetch(conn)
            return 0
        if args.step == "insample":
            out = insample(conn)
            print_insample(out)
        else:
            if not args.unlock_lockbox:
                parser.error("the lockbox needs --unlock-lockbox, and runs once")
            out = lockbox(conn)
            print_lockbox(out)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(store._finite(out), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
