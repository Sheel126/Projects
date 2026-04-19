package com.llmgateway.api.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;

import java.util.List;

/**
 * Canonical chat completion request accepted by the gateway.
 *
 * @param model       provider model identifier, for example {@code gpt-4o}
 * @param messages    ordered conversation turns
 * @param temperature optional sampling temperature
 * @param maxTokens   optional maximum tokens to generate
 * @param userId      logical user id for future rate limiting and attribution
 */
public record ChatRequest(
    @NotBlank String model,
    @NotEmpty @Valid List<Message> messages,
    Double temperature,
    Integer maxTokens,
    String userId
) {
}
