-- liquid-atm baseline schema (Phase 0).
-- Tables are created now so every later phase writes into a schema that was designed up front.
-- Money is NUMERIC (exact decimal), never float: rounding errors in a tax ledger compound.

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Market data & universe (written by quant, Phase 1)
-- ---------------------------------------------------------------------------

CREATE TABLE instruments (
    symbol          TEXT PRIMARY KEY,
    name            TEXT,
    asset_class     TEXT        NOT NULL CHECK (asset_class IN ('us_equity', 'etf')),  -- no options, ever
    exchange        TEXT,
    cik             TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    delisted_on     DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Raw (as-traded) prices plus a cumulative adjustment factor.
-- adjusted_price = raw_price * adj_factor. Stops/limits are placed on RAW prices;
-- returns/indicators are computed on ADJUSTED prices.
CREATE TABLE daily_bars (
    symbol          TEXT          NOT NULL,
    trade_date      DATE          NOT NULL,
    open            NUMERIC(14,4) NOT NULL,
    high            NUMERIC(14,4) NOT NULL,
    low             NUMERIC(14,4) NOT NULL,
    close           NUMERIC(14,4) NOT NULL,
    volume          BIGINT        NOT NULL CHECK (volume >= 0),
    vwap            NUMERIC(14,4),
    adj_factor      NUMERIC(18,10) NOT NULL DEFAULT 1,
    source          TEXT          NOT NULL CHECK (source IN ('alpaca_sip', 'alpaca_iex', 'yfinance')),
    ingested_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, trade_date),
    CHECK (high >= low)
) PARTITION BY RANGE (trade_date);

DO $$
BEGIN
    FOR y IN 2000..2030 LOOP
        EXECUTE format(
            'CREATE TABLE daily_bars_%s PARTITION OF daily_bars FOR VALUES FROM (%L) TO (%L)',
            y, make_date(y, 1, 1), make_date(y + 1, 1, 1));
    END LOOP;
END $$;
CREATE TABLE daily_bars_default PARTITION OF daily_bars DEFAULT;

-- Point-in-time index membership: "what was in the index on as_of_date".
CREATE TABLE universe_membership (
    index_name      TEXT        NOT NULL,          -- 'russell1000', 'sp500'
    as_of_date      DATE        NOT NULL,
    symbol          TEXT        NOT NULL,
    weight          NUMERIC(10,8),
    source          TEXT        NOT NULL,
    PRIMARY KEY (index_name, as_of_date, symbol)
);
CREATE INDEX idx_universe_symbol ON universe_membership (symbol, as_of_date);

CREATE TABLE trading_calendar (
    trade_date      DATE PRIMARY KEY,
    session_open    TIMESTAMPTZ NOT NULL,
    session_close   TIMESTAMPTZ NOT NULL,
    is_early_close  BOOLEAN     NOT NULL DEFAULT FALSE
);

-- ---------------------------------------------------------------------------
-- Intents -> orders -> fills (quant proposes, orchestrator disposes)
-- ---------------------------------------------------------------------------

CREATE TABLE trade_intents (
    id              BIGSERIAL PRIMARY KEY,
    intent_date     DATE          NOT NULL,
    symbol          TEXT          NOT NULL REFERENCES instruments (symbol),
    side            TEXT          NOT NULL CHECK (side = 'buy'),     -- long-only
    entry_limit     NUMERIC(14,4) NOT NULL CHECK (entry_limit > 0),
    take_profit     NUMERIC(14,4) NOT NULL,
    stop_loss       NUMERIC(14,4) NOT NULL,
    risk_fraction   NUMERIC(6,5)  NOT NULL CHECK (risk_fraction > 0 AND risk_fraction <= 0.02),
    regime          TEXT          NOT NULL,
    reason          TEXT          NOT NULL,
    llm_verdict     JSONB,
    status          TEXT          NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'accepted', 'rejected', 'submitted', 'expired')),
    reject_reason   TEXT,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (intent_date, symbol),
    CHECK (stop_loss < entry_limit AND entry_limit < take_profit)
);

CREATE TABLE orders (
    id              BIGSERIAL PRIMARY KEY,
    client_order_id TEXT          NOT NULL UNIQUE,    -- idempotency key sent to Alpaca
    broker_order_id TEXT          UNIQUE,
    intent_id       BIGINT        REFERENCES trade_intents (id),
    parent_id       BIGINT        REFERENCES orders (id),   -- bracket legs point at the entry
    symbol          TEXT          NOT NULL,
    side            TEXT          NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type      TEXT          NOT NULL,           -- limit, stop, market
    order_class     TEXT          NOT NULL,           -- simple, bracket, oco
    qty             NUMERIC(14,4) NOT NULL CHECK (qty > 0),
    limit_price     NUMERIC(14,4),
    stop_price      NUMERIC(14,4),
    time_in_force   TEXT          NOT NULL,
    status          TEXT          NOT NULL,
    submitted_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    broker_payload  JSONB
);
CREATE INDEX idx_orders_symbol_status ON orders (symbol, status);

CREATE TABLE fills (
    id              BIGSERIAL PRIMARY KEY,
    order_id        BIGINT        NOT NULL REFERENCES orders (id),
    broker_fill_id  TEXT          NOT NULL UNIQUE,    -- replayed stream events are ignored
    symbol          TEXT          NOT NULL,
    side            TEXT          NOT NULL CHECK (side IN ('buy', 'sell')),
    qty             NUMERIC(14,4) NOT NULL CHECK (qty > 0),
    price           NUMERIC(14,4) NOT NULL CHECK (price > 0),
    fees            NUMERIC(12,4) NOT NULL DEFAULT 0,
    filled_at       TIMESTAMPTZ   NOT NULL
);
CREATE INDEX idx_fills_symbol_time ON fills (symbol, filled_at);

-- ---------------------------------------------------------------------------
-- Tax ledger (IRC §1091 wash sales, this bot's Alpaca account only)
-- ---------------------------------------------------------------------------

CREATE TABLE tax_lots (
    id                    BIGSERIAL PRIMARY KEY,
    symbol                TEXT          NOT NULL,
    open_fill_id          BIGINT        NOT NULL REFERENCES fills (id),
    acquired_on           DATE          NOT NULL,
    holding_period_start  DATE          NOT NULL,   -- earlier than acquired_on if a washed loss tacked on
    qty_original          NUMERIC(14,4) NOT NULL CHECK (qty_original > 0),
    qty_remaining         NUMERIC(14,4) NOT NULL CHECK (qty_remaining >= 0),
    cost_basis            NUMERIC(14,4) NOT NULL,   -- total, incl. fees and wash-sale adjustments
    wash_adjustment       NUMERIC(14,4) NOT NULL DEFAULT 0,
    closed_on             DATE,
    CHECK (qty_remaining <= qty_original)
);
CREATE INDEX idx_tax_lots_open ON tax_lots (symbol) WHERE qty_remaining > 0;

-- One row per (lot, closing fill): the realized gain/loss event.
CREATE TABLE lot_disposals (
    id                BIGSERIAL PRIMARY KEY,
    lot_id            BIGINT        NOT NULL REFERENCES tax_lots (id),
    close_fill_id     BIGINT        NOT NULL REFERENCES fills (id),
    disposed_on       DATE          NOT NULL,
    qty               NUMERIC(14,4) NOT NULL CHECK (qty > 0),
    proceeds          NUMERIC(14,4) NOT NULL,
    cost_basis        NUMERIC(14,4) NOT NULL,
    gain              NUMERIC(14,4) NOT NULL,       -- proceeds - cost_basis (negative = loss)
    disallowed_loss   NUMERIC(14,4) NOT NULL DEFAULT 0 CHECK (disallowed_loss >= 0),
    is_long_term      BOOLEAN       NOT NULL DEFAULT FALSE,
    exit_reason       TEXT          CHECK (exit_reason IN ('take_profit', 'stop_loss', 'time_stop',
                                                           'december_flush', 'kill_switch', 'manual'))
);
CREATE INDEX idx_disposals_date ON lot_disposals (disposed_on);

-- Links a disallowed loss to the replacement lot whose basis absorbed it.
CREATE TABLE wash_sale_adjustments (
    id                  BIGSERIAL PRIMARY KEY,
    disposal_id         BIGINT        NOT NULL REFERENCES lot_disposals (id),
    replacement_lot_id  BIGINT        NOT NULL REFERENCES tax_lots (id),
    qty                 NUMERIC(14,4) NOT NULL CHECK (qty > 0),
    disallowed_amount   NUMERIC(14,4) NOT NULL CHECK (disallowed_amount > 0),
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE ticker_blacklist (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              TEXT        NOT NULL,
    reason              TEXT        NOT NULL,   -- e.g. 'wash_sale_cooldown'
    blacklisted_on      DATE        NOT NULL,
    until_date          DATE        NOT NULL,   -- tradable again ON this date
    source_disposal_id  BIGINT      REFERENCES lot_disposals (id),
    CHECK (until_date > blacklisted_on)
);
CREATE INDEX idx_blacklist_active ON ticker_blacklist (symbol, until_date);

-- ---------------------------------------------------------------------------
-- Audit & LLM observability
-- ---------------------------------------------------------------------------

-- Append-only, hash-chained: hash = sha256(prev_hash || canonical(event)).
-- Editing or deleting any row breaks every hash after it, so tampering is detectable.
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor           TEXT        NOT NULL,       -- 'orchestrator', 'quant', 'operator'
    event_type      TEXT        NOT NULL,
    payload         JSONB       NOT NULL,
    prev_hash       CHAR(64)    NOT NULL,
    hash            CHAR(64)    NOT NULL UNIQUE
);

CREATE TABLE llm_calls (
    id                  BIGSERIAL PRIMARY KEY,
    called_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    task                TEXT        NOT NULL,
    model               TEXT        NOT NULL,
    prompt_version      TEXT        NOT NULL,
    cache_key           TEXT        NOT NULL,
    cached              BOOLEAN     NOT NULL,
    symbol              TEXT,
    latency_ms          INTEGER     NOT NULL,
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    verdict             JSONB,
    error               TEXT
);
CREATE INDEX idx_llm_calls_symbol ON llm_calls (symbol, called_at);
