-- Phase 2: persisted backtest runs (see docs/lessons/02-backtester-and-tax.md).
--
-- Runs are stored rather than printed because Phase 4 compares hundreds of them: walk-forward
-- folds, CPCV splits and parameter sweeps. `config_hash` is the join key that makes a sweep
-- reproducible, and counting distinct hashes is how the Deflated Sharpe calculation learns how
-- many trials were actually run - the number that decides whether a good result is real.

CREATE TABLE backtest_runs (
    id                      BIGSERIAL PRIMARY KEY,
    run_at                  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    strategy                TEXT          NOT NULL,
    label                   TEXT,                       -- e.g. 'wfa_fold_3', 'baseline'
    config_hash             TEXT          NOT NULL,      -- BacktestConfig.fingerprint()
    config                  JSONB         NOT NULL,
    git_rev                 TEXT,
    start_date              DATE          NOT NULL,
    end_date                DATE          NOT NULL,
    initial_cash            NUMERIC(18,2) NOT NULL,

    final_equity            NUMERIC(18,2) NOT NULL,
    final_equity_after_tax  NUMERIC(18,2) NOT NULL,
    -- Everything sold and every dollar of tax paid. The only number that compares a strategy that
    -- realizes gains every week against SPY buy-and-hold, whose bill is deferred to the very end.
    post_liquidation_value  NUMERIC(18,2) NOT NULL,

    metrics                 JSONB         NOT NULL,      -- pre_tax / after_tax / trades / tax
    diagnostics             JSONB         NOT NULL,      -- ambiguity_rate, touch_fill_rate, ...
    CHECK (end_date >= start_date)
);
CREATE INDEX idx_backtest_runs_hash ON backtest_runs (config_hash, run_at DESC);
CREATE INDEX idx_backtest_runs_strategy ON backtest_runs (strategy, run_at DESC);

-- The equity curve, one row per session. Drawdown and the after-tax curve are recomputed from
-- here rather than trusted from `metrics`, so a stored run can always be re-audited.
CREATE TABLE backtest_equity (
    run_id          BIGINT        NOT NULL REFERENCES backtest_runs (id) ON DELETE CASCADE,
    trade_date      DATE          NOT NULL,
    cash            NUMERIC(18,2) NOT NULL,
    positions_value NUMERIC(18,2) NOT NULL,
    equity          NUMERIC(18,2) NOT NULL,
    tax_reserve     NUMERIC(18,2) NOT NULL,
    equity_after_tax NUMERIC(18,2) NOT NULL,
    tax_paid_cum    NUMERIC(18,2) NOT NULL,
    n_positions     INTEGER       NOT NULL,
    PRIMARY KEY (run_id, trade_date)
);

-- One row per closed round trip. `ambiguous_bar` and `touched_only_entry` are stored per trade,
-- not just aggregated: Phase 4 needs to re-run the numbers with those trades excluded to see how
-- much of the result depends on the two modelling assumptions in lesson 02 §2-§3.
CREATE TABLE backtest_trades (
    id                BIGSERIAL PRIMARY KEY,
    run_id            BIGINT        NOT NULL REFERENCES backtest_runs (id) ON DELETE CASCADE,
    symbol            TEXT          NOT NULL,
    entry_date        DATE          NOT NULL,
    entry_price       NUMERIC(14,4) NOT NULL,
    qty               NUMERIC(14,4) NOT NULL,
    exit_date         DATE,
    exit_price        NUMERIC(14,4),
    exit_reason       TEXT          CHECK (exit_reason IN ('take_profit', 'stop_loss', 'time_stop',
                                                          'december_flush', 'kill_switch',
                                                          'manual')),
    fill_kind         TEXT,          -- gap_stop, gap_target, ambiguous_stop, stop, target, ...
    ambiguous_bar     BOOLEAN       NOT NULL DEFAULT FALSE,
    touched_only_entry BOOLEAN      NOT NULL DEFAULT FALSE,
    days_held         INTEGER       NOT NULL DEFAULT 0,
    gross_pnl         NUMERIC(14,2) NOT NULL DEFAULT 0,
    fees              NUMERIC(12,4) NOT NULL DEFAULT 0,
    realized_gain     NUMERIC(14,2) NOT NULL DEFAULT 0,   -- allowed, after §1091
    disallowed_loss   NUMERIC(14,2) NOT NULL DEFAULT 0,
    is_long_term      BOOLEAN       NOT NULL DEFAULT FALSE,
    reason            TEXT
);
CREATE INDEX idx_backtest_trades_run ON backtest_trades (run_id, entry_date);
CREATE INDEX idx_backtest_trades_symbol ON backtest_trades (symbol, entry_date);
