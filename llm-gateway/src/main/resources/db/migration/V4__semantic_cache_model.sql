ALTER TABLE semantic_cache
    ADD COLUMN IF NOT EXISTS model TEXT;

UPDATE semantic_cache
SET model = COALESCE(request_json->>'model', '')
WHERE model IS NULL;

ALTER TABLE semantic_cache
    ALTER COLUMN model SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_semantic_expires_model
    ON semantic_cache (expires_at, model);
