"""Persist a run into `backtest_runs` / `backtest_equity` / `backtest_trades` (V5).

Same convention as the Phase 1 data layer: functions take an open connection and never commit, so
the caller owns the transaction and a failed write leaves nothing half-stored.
"""

import hashlib
import json
import math
import subprocess
from dataclasses import asdict
from datetime import date

import pandas as pd
import psycopg

from liquid_atm_quant.backtest.engine import BacktestResult
from liquid_atm_quant.backtest.metrics import report


def to_json(value: object) -> str:
    """Serialise for a `jsonb` column.

    Python's `json` happily writes `NaN` and `Infinity`, which Postgres rejects, so the non-finite
    values the metrics module produces deliberately (Calmar with no drawdown, Sortino with no
    downside, profit factor with no losing trade) are stored as SQL NULL. They mean "undefined",
    and NULL is how a database says that.
    """
    return json.dumps(_finite(value), default=str)


def _finite(value: object) -> object:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(v) for v in value]
    return value


def git_revision() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True, timeout=5, check=False)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _config(result: BacktestResult) -> dict:
    config = asdict(result.config)
    if result.strategy_params is not None:
        config["strategy_params"] = result.strategy_params
    return config


def save(conn: psycopg.Connection, result: BacktestResult, label: str | None = None) -> int:
    """Store one run and return its `backtest_runs.id`."""
    metrics = report(result)
    equity = result.equity
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO backtest_runs (strategy, label, config_hash, config, git_rev, start_date,
                                       end_date, initial_cash, final_equity,
                                       final_equity_after_tax, post_liquidation_value, metrics,
                                       diagnostics)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id""",
                    (result.strategy, label, result.config_hash,
                     to_json(_config(result)), git_revision(),
                     equity.index[0], equity.index[-1], result.config.initial_cash,
                     result.final_equity, result.final_equity_after_tax,
                     result.post_liquidation_value, to_json(metrics),
                     to_json(metrics["diagnostics"])))
        run_id = cur.fetchone()[0]

        with cur.copy("COPY backtest_equity (run_id, trade_date, cash, positions_value, equity, "
                      "tax_reserve, equity_after_tax, tax_paid_cum, n_positions) "
                      "FROM STDIN") as copy:
            for trade_date, row in equity.iterrows():
                copy.write_row((run_id, trade_date, row["cash"], row["positions_value"],
                                row["equity"], row["reserve"], row["equity_after_tax"],
                                row["tax_paid_cum"], int(row["n_positions"])))

        cur.executemany("""
            INSERT INTO backtest_trades (run_id, symbol, entry_date, entry_price, qty, exit_date,
                                         exit_price, exit_reason, fill_kind, ambiguous_bar,
                                         touched_only_entry, days_held, gross_pnl, fees,
                                         realized_gain, disallowed_loss, is_long_term, reason,
                                         r_multiple)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s)""",
                        [(run_id, t.symbol, t.entry_date, t.entry_price, t.qty, t.exit_date,
                          t.exit_price, t.exit_reason, t.fill_kind, t.ambiguous_bar,
                          t.touched_only_entry, t.days_held, t.gross_pnl, t.fees, t.realized_gain,
                          t.disallowed_loss, t.is_long_term, t.reason,
                          None if t.r_multiple is None else round(t.r_multiple, 4))
                         for t in result.trades])
    return run_id


def params_hash(params: dict) -> str:
    """The trial identity of a strategy that does not run through the daily engine."""
    payload = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def save_report(conn: psycopg.Connection, strategy: str, params: dict, report_: dict,
                equity: pd.DataFrame, label: str | None = None) -> int:
    """Store a Phase 3d run that was not produced by `Backtester` (intraday, lesson 03d §3).

    `equity` needs `equity`, `reserve`, `equity_after_tax` and `tax_paid_cum` columns. An intraday
    book is flat every night, so cash is the whole equity and there are no positions to report.
    """
    config_hash = params_hash(params)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO backtest_runs (strategy, label, config_hash, config, git_rev, start_date,
                                       end_date, initial_cash, final_equity,
                                       final_equity_after_tax, post_liquidation_value, metrics,
                                       diagnostics)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id""",
                    (strategy, label, config_hash, to_json(params), git_revision(),
                     equity.index[0], equity.index[-1], params.get("initial_cash", 100000.0),
                     float(equity["equity"].iloc[-1]), float(equity["equity_after_tax"].iloc[-1]),
                     report_["post_liquidation_value"], to_json(report_),
                     to_json(report_.get("diagnostics", {}))))
        run_id = cur.fetchone()[0]
        with cur.copy("COPY backtest_equity (run_id, trade_date, cash, positions_value, equity, "
                      "tax_reserve, equity_after_tax, tax_paid_cum, n_positions) "
                      "FROM STDIN") as copy:
            for trade_date, row in equity.iterrows():
                copy.write_row((run_id, trade_date, round(row["equity"], 2), 0,
                                round(row["equity"], 2), round(row["reserve"], 2),
                                round(row["equity_after_tax"], 2), round(row["tax_paid_cum"], 2),
                                0))
    return run_id


def load_equity(conn: psycopg.Connection, run_id: int) -> list[tuple[date, float]]:
    with conn.cursor() as cur:
        cur.execute("SELECT trade_date, equity_after_tax FROM backtest_equity "
                    "WHERE run_id = %s ORDER BY trade_date", (run_id,))
        return [(row[0], float(row[1])) for row in cur.fetchall()]


def trial_count(conn: psycopg.Connection, strategy: str) -> int:
    """Distinct configurations ever run for this strategy.

    Phase 4's Deflated Sharpe needs the number of trials, and the honest count is every parameter
    set that was ever tried - not the number that were kept.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT count(DISTINCT config_hash) FROM backtest_runs WHERE strategy = %s",
                    (strategy,))
        return int(cur.fetchone()[0])
