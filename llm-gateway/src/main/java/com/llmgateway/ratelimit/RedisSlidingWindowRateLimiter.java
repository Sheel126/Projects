package com.llmgateway.ratelimit;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * Sliding-window rate limiter using a Redis sorted set and an atomic Lua script.
 *
 * <p>Algorithm: store each request timestamp (ms) as a ZSET score, evict entries older than the window,
 * count remaining entries, and only add the new entry if under the limit.</p>
 */
@Component
public class RedisSlidingWindowRateLimiter {

    private static final String KEY_PREFIX = "llm:rl:v1:";

    private static final DefaultRedisScript<Long> SCRIPT = new DefaultRedisScript<>(
        // KEYS[1] = zset key
        // ARGV[1] = nowMs
        // ARGV[2] = windowMs
        // ARGV[3] = limit
        // ARGV[4] = member
        // ARGV[5] = expireSeconds
        """
            local key = KEYS[1]
            local nowMs = tonumber(ARGV[1])
            local windowMs = tonumber(ARGV[2])
            local limit = tonumber(ARGV[3])
            local member = ARGV[4]
            local expireSeconds = tonumber(ARGV[5])

            redis.call('ZREMRANGEBYSCORE', key, 0, nowMs - windowMs)
            local count = redis.call('ZCARD', key)
            if count >= limit then
              return -1
            end
            redis.call('ZADD', key, nowMs, member)
            redis.call('EXPIRE', key, expireSeconds)
            return limit - (count + 1)
            """,
        Long.class
    );

    private final StringRedisTemplate redis;

    public RedisSlidingWindowRateLimiter(StringRedisTemplate redis) {
        this.redis = redis;
    }

    public RateLimitResult checkAndConsume(UUID apiKeyId, int limit, int windowSeconds) {
        return checkAndConsume(KEY_PREFIX + apiKeyId, limit, windowSeconds);
    }

    public RateLimitResult checkAndConsume(String bucketKey, int limit, int windowSeconds) {
        long nowMs = Instant.now().toEpochMilli();
        long windowMs = Math.max(1, windowSeconds) * 1000L;
        String member = nowMs + "-" + java.util.UUID.randomUUID();
        int expireSeconds = Math.max(1, windowSeconds + 2);

        Long remaining = redis.execute(
            SCRIPT,
            List.of(bucketKey),
            Long.toString(nowMs),
            Long.toString(windowMs),
            Integer.toString(Math.max(0, limit)),
            member,
            Integer.toString(expireSeconds)
        );

        if (remaining == null) {
            return RateLimitResult.allowUnknown();
        }
        if (remaining < 0) {
            return RateLimitResult.blocked(limit, windowSeconds);
        }
        return RateLimitResult.allowed(limit, windowSeconds, remaining);
    }
}

