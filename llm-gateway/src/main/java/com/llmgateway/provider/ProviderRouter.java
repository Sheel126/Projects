package com.llmgateway.provider;

import com.llmgateway.api.dto.ChatRequest;
import com.llmgateway.api.dto.ChatResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.Comparator;
import java.util.List;
/**
 * Selects a provider for a model and performs best-effort failover when the primary is unhealthy.
 */
@Service
public class ProviderRouter {

    private static final Logger log = LoggerFactory.getLogger(ProviderRouter.class);

    private final List<LlmProvider> providers;
    private final ModelTranslator modelTranslator;

    /**
     * Creates a router backed by all discovered providers.
     *
     * @param providers       available providers
     * @param modelTranslator model mapping for failover
     */
    public ProviderRouter(List<LlmProvider> providers, ModelTranslator modelTranslator) {
        this.providers = providers.stream()
            .sorted(Comparator.comparing(LlmProvider::name))
            .toList();
        this.modelTranslator = modelTranslator;
    }

    /**
     * Routes to the provider that handles the requested model.
     * Falls back to an alternate provider if primary is unhealthy.
     *
     * @param request canonical request
     * @return canonical response
     */
    public ChatResponse route(ChatRequest request) {
        LlmProvider primary = resolvePrimary(request.model());
        if (primary.isHealthy()) {
            return primary.complete(request);
        }
        return fallback(request, primary);
    }

    private LlmProvider resolvePrimary(String model) {
        return providers.stream()
            .filter(p -> p.supportsModel(model))
            .findFirst()
            .orElseThrow(() -> new ProviderException(
                "model.unsupported",
                "No provider registered for model: " + model
            ));
    }

    private ChatResponse fallback(ChatRequest request, LlmProvider failed) {
        for (LlmProvider candidate : providers) {
            if (candidate == failed || !candidate.isHealthy()) {
                continue;
            }
            var mapped = modelTranslator.translateForProvider(candidate.name(), request.model());
            if (mapped.isEmpty()) {
                continue;
            }
            ChatRequest translated = new ChatRequest(
                mapped.get(),
                request.messages(),
                request.temperature(),
                request.maxTokens(),
                request.userId()
            );
            if (!candidate.supportsModel(translated.model())) {
                continue;
            }
            log.warn("provider.failover from={} to={} model={} translatedModel={}",
                failed.name(), candidate.name(), request.model(), translated.model());
            return candidate.complete(translated);
        }
        throw new ProviderException(
            "provider.unavailable",
            "Primary provider unhealthy and no healthy failover target for model: " + request.model()
        );
    }
}
