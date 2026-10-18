-- Identity segments. A ticker can outlive the company that used it: CTRA was Contura Energy
-- until 2021-02-03 and Coterra Energy from 2021-10-04; BBBY, CA, CAM, APC and ~70 others were
-- reused the same way. Splitting each symbol's real bars at long gaps gives each identity its own
-- segment_id, so no indicator window (ATR, breakout high, momentum) may span two companies.
CREATE VIEW bar_segments AS
    WITH cal AS (
        SELECT trade_date, row_number() OVER (ORDER BY trade_date) AS rn FROM trading_calendar),
    seq AS (
        SELECT b.*, c.rn,
               lag(c.rn) OVER (PARTITION BY b.symbol ORDER BY b.trade_date) AS prev_rn
        FROM tradable_bars b JOIN cal c USING (trade_date))
    SELECT symbol, trade_date, open, high, low, close, volume, vwap, adj_factor, source,
           sum(CASE WHEN prev_rn IS NULL OR rn - prev_rn - 1 > 20 THEN 1 ELSE 0 END)
               OVER (PARTITION BY symbol ORDER BY trade_date) AS segment_id
    FROM seq;

COMMENT ON VIEW bar_segments IS
    'tradable_bars with a segment_id that increments after a gap of more than 20 sessions. '
    'Phase 2+ computes indicators within a single (symbol, segment_id).';
