-- Phase 2: two exit reasons the baselines need.
--
-- A monthly rebalance and the backtester's terminal liquidation were both landing in 'manual',
-- which made `exit_reasons` useless as a diagnostic: a 288-trade momentum run reported 288 manual
-- exits. Phase 4 reads that breakdown to tell a strategy's real exits apart from bookkeeping ones,
-- so they get their own names.
--
-- 'rebalance'           - a target-weight strategy rotated out of the name.
-- 'terminal_liquidation'- the backtest ended and everything was sold to settle the tax bill
--                         (lesson 02 §9). It never occurs in live trading.

ALTER TABLE lot_disposals DROP CONSTRAINT lot_disposals_exit_reason_check;
ALTER TABLE lot_disposals ADD CONSTRAINT lot_disposals_exit_reason_check
    CHECK (exit_reason IN ('take_profit', 'stop_loss', 'time_stop', 'december_flush',
                           'kill_switch', 'manual', 'rebalance', 'terminal_liquidation'));

ALTER TABLE backtest_trades DROP CONSTRAINT backtest_trades_exit_reason_check;
ALTER TABLE backtest_trades ADD CONSTRAINT backtest_trades_exit_reason_check
    CHECK (exit_reason IN ('take_profit', 'stop_loss', 'time_stop', 'december_flush',
                           'kill_switch', 'manual', 'rebalance', 'terminal_liquidation'));
