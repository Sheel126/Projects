CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE semantic_cache (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_hash     TEXT NOT NULL,
    embedding       vector(1536) NOT NULL,
    request_json    JSONB NOT NULL,
    response_json   JSONB NOT NULL,
    hit_count       INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_semantic_embedding ON semantic_cache
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
