-- Phase 3b: point-in-time company fundamentals from SEC XBRL "company facts" (lesson 03b §2).
--
-- One row per (company, normalized concept, period) holding the value AS FIRST REPORTED, with
-- the date it was filed. Later restatements and the prior-year comparatives that every 10-K
-- repeats are deliberately dropped: a backtest may only use what the market could read on the
-- day, and a restated number did not exist yet.
--
-- `concept` is our normalized name (revenue, net_income, equity, ...), `source_tag` the us-gaap
-- or dei tag it came from. Duration facts carry period_start; instants (balance sheet, share
-- counts) leave it NULL.
--
-- A strategy at the close of day D may use a row only when filed < D: the filing date has no
-- time of day, and a filing accepted after the close is not tradable until the next session.

CREATE TABLE fundamental_facts (
    cik          TEXT        NOT NULL,
    concept      TEXT        NOT NULL,
    period_start DATE,
    period_end   DATE        NOT NULL,
    value        NUMERIC     NOT NULL,
    filed        DATE        NOT NULL,
    form         TEXT,
    accn         TEXT,
    source_tag   TEXT        NOT NULL
);

CREATE UNIQUE INDEX uq_fundamental_facts
    ON fundamental_facts (cik, concept, period_end, COALESCE(period_start, DATE '0001-01-01'));
CREATE INDEX idx_fundamental_facts_cik_filed ON fundamental_facts (cik, filed);

-- How each symbol was tied to its CIK: 'ticker' (SEC's current ticker map) or 'name' (Alpaca's
-- company name matched to the XBRL entity name - how delisted companies get their history back).
ALTER TABLE instruments ADD COLUMN cik_source TEXT;
