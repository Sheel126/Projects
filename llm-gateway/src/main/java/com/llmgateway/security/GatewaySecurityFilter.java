package com.llmgateway.security;

import com.llmgateway.api.AuthException;
import com.llmgateway.api.RateLimitException;
import com.llmgateway.config.GatewaySecurityProperties;
import com.llmgateway.ratelimit.RateLimitResult;
import com.llmgateway.ratelimit.RedisSlidingWindowRateLimiter;
import io.micrometer.core.instrument.MeterRegistry;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Optional;
import java.util.UUID;

/**
 * Phase 3: API key auth and sliding-window rate limiting.
 */
@Component
@Order(10)
public class GatewaySecurityFilter extends OncePerRequestFilter {

    private final GatewaySecurityProperties props;
    private final ApiKeyService apiKeyService;
    private final RedisSlidingWindowRateLimiter rateLimiter;
    private final MeterRegistry meterRegistry;

    public GatewaySecurityFilter(
        GatewaySecurityProperties props,
        ApiKeyService apiKeyService,
        RedisSlidingWindowRateLimiter rateLimiter,
        ObjectProvider<MeterRegistry> meterRegistry
    ) {
        this.props = props;
        this.apiKeyService = apiKeyService;
        this.rateLimiter = rateLimiter;
        this.meterRegistry = meterRegistry.getIfAvailable();
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        if (path == null) {
            return true;
        }
        return !(path.startsWith("/v1/"))
            || path.startsWith("/v1/admin/")
            || path.equals("/health")
            || path.startsWith("/actuator/")
            || path.startsWith("/swagger-ui")
            || path.startsWith("/v3/api-docs");
    }

    @Override
    protected void doFilterInternal(
        HttpServletRequest request,
        HttpServletResponse response,
        FilterChain filterChain
    ) throws ServletException, IOException {

        Optional<ApiKeyPrincipal> principal = Optional.empty();
        if (props.auth().enabled()) {
            String header = props.auth().headerName();
            String raw = request.getHeader(header);
            if (!StringUtils.hasText(raw)) {
                increment("auth", "missing");
                throw new AuthException("auth.missing", "Missing API key header: " + header);
            }
            principal = apiKeyService.authenticate(raw);
            if (principal.isEmpty()) {
                increment("auth", "invalid");
                throw new AuthException("auth.invalid", "Invalid or revoked API key");
            }
            ApiKeyPrincipal p = principal.get();
            request.setAttribute("apiKeyId", p.id());
            request.setAttribute("userId", p.userId());
        }

        if (props.rateLimit().enabled()) {
            int windowSeconds = Math.max(1, props.rateLimit().windowSeconds());
            int limit = principal.map(ApiKeyPrincipal::rateLimitRpm).orElse(props.rateLimit().defaultRpm());
            String bucketKey = principal
                .map(p -> "llm:rl:v1:" + p.id())
                .orElseGet(() -> "llm:rl:v1:anon:" + clientIp(request));

            RateLimitResult result = rateLimiter.checkAndConsume(bucketKey, limit, windowSeconds);
            if (!result.allowed()) {
                increment("ratelimit", "blocked");
                throw new RateLimitException("Too many requests", result.retryAfterSeconds() == null ? windowSeconds : result.retryAfterSeconds());
            }
            increment("ratelimit", "allowed");
            if (result.limit() != null) {
                response.setHeader("X-RateLimit-Limit", Integer.toString(result.limit()));
            }
            if (result.remaining() != null) {
                response.setHeader("X-RateLimit-Remaining", Long.toString(result.remaining()));
            }
            if (result.windowSeconds() != null) {
                response.setHeader("X-RateLimit-Window-Seconds", Integer.toString(result.windowSeconds()));
            }
        }

        filterChain.doFilter(request, response);
    }

    private void increment(String name, String outcome) {
        if (meterRegistry != null) {
            meterRegistry.counter("llm.gateway." + name, "result", outcome).increment();
        }
    }

    private static String clientIp(HttpServletRequest request) {
        String forwarded = request.getHeader("X-Forwarded-For");
        if (StringUtils.hasText(forwarded)) {
            String first = forwarded.split(",")[0].trim();
            if (!first.isEmpty()) {
                return first;
            }
        }
        String remote = request.getRemoteAddr();
        return remote == null ? "unknown" : remote;
    }
}

