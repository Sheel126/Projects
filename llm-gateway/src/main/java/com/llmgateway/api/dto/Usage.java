package com.llmgateway.api.dto;

/**
 * Token usage reported by the upstream provider.
 *
 * @param promptTokens     tokens consumed by the prompt
 * @param completionTokens tokens generated in the completion
 * @param totalTokens      total tokens if the provider reports it, otherwise derived
 */
public record Usage(
    int promptTokens,
    int completionTokens,
    int totalTokens
) {
}
