package com.llmgateway.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Configuration for Phase 2 response caching (Redis exact + pgvector semantic).
 *
 * @param exactEnabled                 when false, exact Redis lookups and writes are skipped
 * @param semanticEnabled              when false, semantic cache is skipped entirely
 * @param exactTtlSeconds              TTL for exact cache entries in Redis (0 disables TTL writes)
 * @param semanticTtlSeconds           TTL for semantic rows in Postgres (defaults to exact TTL when unset)
 * @param semanticSimilarityThreshold  minimum cosine similarity (0–1) required for a semantic hit
 * @param embeddingModel               OpenAI embeddings model id (must emit 1536 dimensions for current schema)
 */
@ConfigurationProperties(prefix = "llm.cache")
public record CacheProperties(
    boolean exactEnabled,
    boolean semanticEnabled,
    int exactTtlSeconds,
    int semanticTtlSeconds,
    double semanticSimilarityThreshold,
    String embeddingModel
) {
}
