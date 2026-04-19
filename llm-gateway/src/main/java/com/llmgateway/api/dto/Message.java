package com.llmgateway.api.dto;

import jakarta.validation.constraints.NotBlank;

/**
 * A single chat message in the gateway's canonical chat format.
 *
 * @param role    conversational role, for example {@code user}, {@code assistant}, or {@code system}
 * @param content message body text
 */
public record Message(
    @NotBlank String role,
    @NotBlank String content
) {
}
