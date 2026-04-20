package com.llmgateway.api.dto;

/**
 * Canonical chat completion response returned by the gateway for every provider.
 *
 * @param id provider-issued completion id when available
 * @param model       model that produced the completion
 * @param provider    provider id that handled the request, for example {@code openai}
 * @param choice      primary assistant message
 * @param usage       token accounting
 * @param fromCache   whether the payload was served from a cache layer
 * @param latencyMs   observed gateway-side latency for the operation
 */
public record ChatResponse(
    String id,
    String model,
    String provider,
    Choice choice,
    Usage usage,
    boolean fromCache,
    long latencyMs
) {

    /**
     * Returns a copy with cache metadata and measured latency (for example a Redis/pgvector lookup).
     *
     * @param fromCache whether the payload was served from cache
     * @param latencyMs gateway-observed latency for this operation in milliseconds
     * @return new response instance
     */
    public ChatResponse withFromCacheAndLatency(boolean fromCache, long latencyMs) {
        return new ChatResponse(id, model, provider, choice, usage, fromCache, latencyMs);
    }
}
