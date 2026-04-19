package com.llmgateway.api.dto;

/**
 * Standard error envelope for API failures.
 *
 * @param code    stable machine-readable error code
 * @param message human-readable explanation
 */
public record ErrorResponse(
    String code,
    String message
) {
}
