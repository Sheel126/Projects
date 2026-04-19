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
}
