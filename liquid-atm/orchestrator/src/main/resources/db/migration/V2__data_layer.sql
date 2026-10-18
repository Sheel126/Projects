-- Phase 1: free data layer (see docs/lessons/01-data-layer.md).

-- Indices like ^VIX are data-only instruments; they can never be traded (intents FK still
-- points here, but the orchestrator's risk gate only accepts us_equity/etf).
ALTER TABLE instruments DROP CONSTRAINT instruments_asset_class_check;
ALTER TABLE instruments ADD CONSTRAINT instruments_asset_class_check
    CHECK (asset_class IN ('us_equity', 'etf', 'index'));
ALTER TABLE instruments ADD COLUMN sector TEXT;
ALTER TABLE instruments ADD COLUMN tradable BOOLEAN NOT NULL DEFAULT TRUE;

-- One row per imported snapshot, so "latest snapshot <= t" is a cheap lookup.
CREATE TABLE universe_snapshots (
    index_name      TEXT        NOT NULL,
    as_of_date      DATE        NOT NULL,
    source          TEXT        NOT NULL,    -- 'ishares_live', 'ishares_wayback', 'fja05680_sp500'
    member_count    INTEGER     NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (index_name, as_of_date)
);

CREATE TABLE data_quality_issues (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID        NOT NULL,
    run_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    check_name      TEXT        NOT NULL,
    severity        TEXT        NOT NULL CHECK (severity IN ('info', 'warn', 'error')),
    symbol          TEXT,
    trade_date      DATE,
    detail          JSONB       NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX idx_dq_run ON data_quality_issues (run_id, severity);

-- SEC ticker <-> CIK map (CIKs are never reused, tickers are).
CREATE TABLE sec_companies (
    cik             TEXT PRIMARY KEY,           -- zero-padded to 10 digits
    ticker          TEXT        NOT NULL,
    title           TEXT        NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sec_companies_ticker ON sec_companies (ticker);

CREATE TABLE sec_filings (
    accession_no     TEXT PRIMARY KEY,
    cik              TEXT        NOT NULL,
    form             TEXT        NOT NULL,
    filed_on         DATE        NOT NULL,
    accepted_at      TIMESTAMPTZ NOT NULL,     -- point-in-time: public from this instant
    report_date      DATE,
    items            TEXT,                     -- 8-K item codes, e.g. '2.02,9.01'
    primary_document TEXT,
    url              TEXT        NOT NULL
);
CREATE INDEX idx_sec_filings_cik_time ON sec_filings (cik, accepted_at);
