package com.llmgateway.cache;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.llmgateway.api.dto.ChatRequest;
import com.llmgateway.api.dto.ChatResponse;
import com.llmgateway.config.CacheProperties;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.Optional;

/**
 * Redis-backed exact match cache for canonical {@link ChatRequest} payloads.
 */
@Component
public class ExactResponseCache {

    private static final Logger log = LoggerFactory.getLogger(ExactResponseCache.class);
    private static final String KEY_PREFIX = "llm:exact:v1:";

    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;
    private final CacheProperties cacheProperties;
    private final MeterRegistry meterRegistry;

    /**
     * Creates the exact cache.
     *
     * @param redis             string template
     * @param objectMapper      JSON mapper
     * @param cacheProperties   cache configuration
     * @param meterRegistry     metrics registry (optional)
     */
    public ExactResponseCache(
        StringRedisTemplate redis,
        ObjectMapper objectMapper,
        CacheProperties cacheProperties,
        ObjectProvider<MeterRegistry> meterRegistry
    ) {
        this.redis = redis;
        this.objectMapper = objectMapper;
        this.cacheProperties = cacheProperties;
        this.meterRegistry = meterRegistry.getIfAvailable();
    }

    /**
     * Attempts to read a cached response for the request.
     *
     * @param request canonical request
     * @return cached response when present
     */
    public Optional<ChatResponse> getIfPresent(ChatRequest request) {
        if (!cacheProperties.exactEnabled() || cacheProperties.exactTtlSeconds() <= 0) {
            return Optional.empty();
        }
        String key = KEY_PREFIX + RequestCanonicalizer.sha256Hex(objectMapper, request);
        try {
            String json = redis.opsForValue().get(key);
            if (json == null || json.isEmpty()) {
                increment("miss");
                return Optional.empty();
            }
            ChatResponse parsed = objectMapper.readValue(json, ChatResponse.class);
            increment("hit");
            return Optional.of(parsed);
        } catch (Exception ex) {
            log.warn("Exact cache read failed; continuing without cache", ex);
            increment("error");
            return Optional.empty();
        }
    }

    /**
     * Stores a live response for future exact hits.
     *
     * @param request  canonical request
     * @param response live provider response
     */
    public void put(ChatRequest request, ChatResponse response) {
        if (!cacheProperties.exactEnabled() || cacheProperties.exactTtlSeconds() <= 0) {
            return;
        }
        String key = KEY_PREFIX + RequestCanonicalizer.sha256Hex(objectMapper, request);
        try {
            String json = objectMapper.writeValueAsString(response);
            redis.opsForValue().set(key, json, Duration.ofSeconds(cacheProperties.exactTtlSeconds()));
            increment("write");
        } catch (Exception ex) {
            log.warn("Exact cache write failed", ex);
            increment("error");
        }
    }

    private void increment(String outcome) {
        if (meterRegistry != null) {
            meterRegistry.counter("llm.cache.exact", "result", outcome).increment();
        }
    }
}
