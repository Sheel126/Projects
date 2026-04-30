package com.llmgateway.security;

import java.util.UUID;

/**
 * Authenticated API key identity and limits.
 *
 * @param id api key id (database primary key)
 * @param userId logical owner / tenant id
 * @param rateLimitRpm requests per minute allowed for this key
 */
public record ApiKeyPrincipal(
    UUID id,
    String userId,
    int rateLimitRpm
) {
}

