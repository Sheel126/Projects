-- Runs once when the Postgres volume is first created.
-- pgvector is used from Phase 5 (retrieval of related filings); enabling it now keeps the image choice honest.
CREATE EXTENSION IF NOT EXISTS vector;
