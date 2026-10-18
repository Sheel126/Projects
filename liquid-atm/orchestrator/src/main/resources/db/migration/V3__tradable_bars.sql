-- Alpaca pads a delisted symbol with frozen placeholder bars (O=H=L=C of the last real trade,
-- volume 0) for every session afterwards - EMC was acquired by Dell on 2016-09-07 and still
-- "prints" 29.05 today. Those rows are not prices anyone could trade, and they also hide gaps
-- that reveal ticker reuse. Everything downstream (signals, backtests, screener) reads this view.
CREATE VIEW tradable_bars AS
    SELECT * FROM daily_bars WHERE volume > 0;

COMMENT ON VIEW tradable_bars IS
    'daily_bars minus zero-volume placeholder/halt rows. Indices such as ^VIX report zero volume '
    'by construction and are therefore absent here: read daily_bars directly for those.';

-- When a symbol stopped trading under its current identity (set by the `delistings` job).
COMMENT ON COLUMN instruments.delisted_on IS
    'Last real (volume > 0) session before a long frozen-padding run; NULL while still trading.';
