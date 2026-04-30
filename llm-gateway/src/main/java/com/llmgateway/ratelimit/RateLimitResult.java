package com.llmgateway.ratelimit;

public record RateLimitResult(
    boolean allowed,
    Integer limit,
    Integer windowSeconds,
    Long remaining,
    Long retryAfterSeconds
) {
    static RateLimitResult allowed(int limit, int windowSeconds, long remaining) {
        return new RateLimitResult(true, limit, windowSeconds, remaining, null);
    }

    static RateLimitResult blocked(int limit, int windowSeconds) {
        long retryAfter = Math.max(1, windowSeconds);
        return new RateLimitResult(false, limit, windowSeconds, 0L, retryAfter);
    }

    static RateLimitResult allowUnknown() {
        return new RateLimitResult(true, null, null, null, null);
    }
}

