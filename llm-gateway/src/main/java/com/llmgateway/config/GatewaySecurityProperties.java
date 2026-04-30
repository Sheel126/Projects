package com.llmgateway.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Phase 3 security configuration: API key auth + rate limiting.
 *
 * <p>Values are intentionally environment-friendly and can be fully disabled for local dev.</p>
 *
 * @param auth auth settings
 * @param rateLimit rate limit settings
 */
@ConfigurationProperties(prefix = "gateway.security")
public record GatewaySecurityProperties(
    Auth auth,
    RateLimit rateLimit
) {
    public record Auth(
        boolean enabled,
        String headerName,
        String hmacSecret,
        String adminToken
    ) {
    }

    public record RateLimit(
        boolean enabled,
        int defaultRpm,
        int windowSeconds
    ) {
    }
}

