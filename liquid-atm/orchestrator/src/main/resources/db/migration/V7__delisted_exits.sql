-- Phase 3: a position whose company stopped trading has to leave the book.
--
-- Found by the first funnel run. A name acquired while held (NorthStar in 2017, Juno, Worldpay,
-- Legg Mason, Extended Stay...) simply has no more bars, so its bracket never resolved: the
-- position sat in the book for years holding a slot and its capital, and in one case (DCT) the
-- ticker was later reused and the *new* company's price hit the old stop. The engine now closes
-- such a position at its last known price after several sessions with no bar from the same
-- corporate identity (lesson 03, "the zombie-position defect").
--
-- 'delisted' - the position was cashed out because its security stopped trading.
--
-- r_multiple is stored per trade so Phase 4 can study the R distribution without rerunning.

ALTER TABLE lot_disposals DROP CONSTRAINT lot_disposals_exit_reason_check;
ALTER TABLE lot_disposals ADD CONSTRAINT lot_disposals_exit_reason_check
    CHECK (exit_reason IN ('take_profit', 'stop_loss', 'time_stop', 'december_flush',
                           'kill_switch', 'manual', 'rebalance', 'terminal_liquidation',
                           'delisted'));

ALTER TABLE backtest_trades DROP CONSTRAINT backtest_trades_exit_reason_check;
ALTER TABLE backtest_trades ADD CONSTRAINT backtest_trades_exit_reason_check
    CHECK (exit_reason IN ('take_profit', 'stop_loss', 'time_stop', 'december_flush',
                           'kill_switch', 'manual', 'rebalance', 'terminal_liquidation',
                           'delisted'));

ALTER TABLE backtest_trades ADD COLUMN r_multiple NUMERIC(10,4);
