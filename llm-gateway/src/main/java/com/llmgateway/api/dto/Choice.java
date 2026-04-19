package com.llmgateway.api.dto;

/**
 * The primary completion choice returned to callers.
 *
 * @param role          role of the assistant message
 * @param content       generated text
 * @param finishReason  provider-specific stop reason when present
 */
public record Choice(
    String role,
    String content,
    String finishReason
) {
}
