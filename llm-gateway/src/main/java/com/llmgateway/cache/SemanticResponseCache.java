package com.llmgateway.cache;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.llmgateway.api.dto.ChatRequest;
import com.llmgateway.api.dto.ChatResponse;
import com.llmgateway.config.CacheProperties;
import com.llmgateway.config.LlmProperties;
import io.micrometer.core.instrument.MeterRegistry;
import org.postgresql.util.PGobject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.UUID;

/**
 * pgvector-backed semantic cache using cosine similarity on OpenAI embeddings.
 */
@Component
public class SemanticResponseCache {

    private static final Logger log = LoggerFactory.getLogger(SemanticResponseCache.class);

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;
    private final CacheProperties cacheProperties;
    private final LlmProperties llmProperties;
    private final MeterRegistry meterRegistry;

    /**
     * Creates the semantic cache repository.
     *
     * @param jdbcTemplate      JDBC access
     * @param objectMapper      JSON mapper
     * @param cacheProperties   cache configuration
     * @param llmProperties     provider configuration (OpenAI key gate)
     * @param meterRegistry     metrics registry (optional)
     */
    public SemanticResponseCache(
        JdbcTemplate jdbcTemplate,
        ObjectMapper objectMapper,
        CacheProperties cacheProperties,
        LlmProperties llmProperties,
        ObjectProvider<MeterRegistry> meterRegistry
    ) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
        this.cacheProperties = cacheProperties;
        this.llmProperties = llmProperties;
        this.meterRegistry = meterRegistry.getIfAvailable();
    }

    /**
     * Whether semantic caching should run for this process.
     *
     * @return true when enabled and OpenAI credentials exist for embeddings
     */
    public boolean isActive() {
        return cacheProperties.semanticEnabled()
            && StringUtils.hasText(llmProperties.openai().apiKey());
    }

    /**
     * Looks up a semantically similar prior response.
     *
     * @param request   canonical request
     * @param embedding query embedding (1536-d)
     * @return cached response JSON when similarity clears the threshold
     */
    public Optional<ChatResponse> lookup(ChatRequest request, float[] embedding) {
        if (!isActive() || embedding == null || embedding.length != 1536) {
            return Optional.empty();
        }
        PGobject vector = toVectorObject(embedding);
        try {
            List<Hit> rows = jdbcTemplate.query(
                """
                    SELECT id, response_json
                    FROM semantic_cache
                    WHERE expires_at > now()
                      AND model = ?
                      AND (1 - (embedding <=> ?::vector)) >= ?
                    ORDER BY embedding <=> ?::vector
                    LIMIT 1
                    """,
                ps -> {
                    ps.setString(1, request.model());
                    ps.setObject(2, vector);
                    ps.setDouble(3, cacheProperties.semanticSimilarityThreshold());
                    ps.setObject(4, vector);
                },
                (rs, rowNum) -> new Hit(rs.getObject("id", UUID.class), rs.getString("response_json"))
            );
            if (rows.isEmpty()) {
                increment("miss");
                return Optional.empty();
            }
            Hit hit = rows.getFirst();
            jdbcTemplate.update("UPDATE semantic_cache SET hit_count = hit_count + 1 WHERE id = ?", hit.id());
            ChatResponse parsed = objectMapper.readValue(hit.responseJson(), ChatResponse.class);
            increment("hit");
            return Optional.of(parsed);
        } catch (Exception ex) {
            log.warn("Semantic cache lookup failed; continuing without cache", ex);
            increment("error");
            return Optional.empty();
        }
    }

    /**
     * Persists a semantic cache entry for a successful completion.
     *
     * @param request   canonical request
     * @param response  live response
     * @param embedding embedding for the prompt text
     */
    public void store(ChatRequest request, ChatResponse response, float[] embedding) {
        if (!isActive() || embedding == null || embedding.length != 1536) {
            return;
        }
        PGobject vector = toVectorObject(embedding);
        try {
            PGobject requestJson = new PGobject();
            requestJson.setType("jsonb");
            requestJson.setValue(objectMapper.writeValueAsString(request));

            PGobject responseJson = new PGobject();
            responseJson.setType("jsonb");
            responseJson.setValue(objectMapper.writeValueAsString(response));

            int ttlSeconds = cacheProperties.semanticTtlSeconds() > 0
                ? cacheProperties.semanticTtlSeconds()
                : cacheProperties.exactTtlSeconds();
            Instant expires = Instant.now().plusSeconds(Math.max(1, ttlSeconds));
            jdbcTemplate.update(
                """
                    INSERT INTO semantic_cache (prompt_hash, embedding, request_json, response_json, expires_at, model)
                    VALUES (?, ?::vector, ?::jsonb, ?::jsonb, ?::timestamptz, ?)
                    """,
                RequestCanonicalizer.promptHash(request),
                vector,
                requestJson,
                responseJson,
                Timestamp.from(expires),
                request.model()
            );
            increment("write");
        } catch (Exception ex) {
            log.warn("Semantic cache write failed", ex);
            increment("error");
        }
    }

    private void increment(String outcome) {
        if (meterRegistry != null) {
            meterRegistry.counter("llm.cache.semantic", "result", outcome).increment();
        }
    }

    private static PGobject toVectorObject(float[] embedding) {
        try {
            PGobject pg = new PGobject();
            pg.setType("vector");
            pg.setValue(toVectorLiteral(embedding));
            return pg;
        } catch (Exception ex) {
            throw new IllegalStateException("Unable to build pgvector literal", ex);
        }
    }

    private static String toVectorLiteral(float[] embedding) {
        StringBuilder sb = new StringBuilder(embedding.length * 12);
        sb.append('[');
        for (int i = 0; i < embedding.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(String.format(Locale.US, "%.8f", embedding[i]));
        }
        sb.append(']');
        return sb.toString();
    }

    private record Hit(UUID id, String responseJson) {
    }
}
