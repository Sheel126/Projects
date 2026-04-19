CREATE TABLE api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash    TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    rate_limit  INTEGER NOT NULL DEFAULT 100,
    monthly_budget_usd NUMERIC(10,4),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at  TIMESTAMPTZ
);
