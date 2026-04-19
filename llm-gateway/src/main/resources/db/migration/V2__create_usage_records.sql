CREATE TABLE usage_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id      UUID NOT NULL REFERENCES api_keys(id),
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    prompt_tokens   INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    cost_usd        NUMERIC(10,6) NOT NULL,
    cache_hit       BOOLEAN NOT NULL DEFAULT false,
    latency_ms      INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_usage_api_key_created ON usage_records(api_key_id, created_at DESC);
CREATE INDEX idx_usage_created ON usage_records(created_at DESC);
