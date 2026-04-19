package com.llmgateway.observability;

import com.llmgateway.provider.LlmProvider;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Surfaces per-provider availability on the Actuator health endpoint.
 */
@Component
public class ProviderHealthIndicator implements HealthIndicator {

    private final List<LlmProvider> providers;

    /**
     * Creates the indicator with all registered providers.
     *
     * @param providers discovered {@link LlmProvider} beans
     */
    public ProviderHealthIndicator(List<LlmProvider> providers) {
        this.providers = providers;
    }

    /**
     * Builds a composite health object with one detail entry per provider.
     *
     * @return health snapshot
     */
    @Override
    public Health health() {
        Health.Builder builder = Health.up();
        for (LlmProvider p : providers) {
            builder.withDetail(p.name(), p.isHealthy() ? "UP" : "DOWN");
        }
        return builder.build();
    }
}
