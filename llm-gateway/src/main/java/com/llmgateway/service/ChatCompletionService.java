package com.llmgateway.service;

import com.llmgateway.api.dto.ChatRequest;
import com.llmgateway.api.dto.ChatResponse;
import com.llmgateway.cache.ExactResponseCache;
import com.llmgateway.cache.OpenAiEmbeddingClient;
import com.llmgateway.cache.RequestCanonicalizer;
import com.llmgateway.cache.SemanticResponseCache;
import com.llmgateway.provider.ProviderRouter;
import org.springframework.stereotype.Service;

import java.util.Optional;

/**
 * Orchestrates chat completions with Phase 2 exact (Redis) and semantic (pgvector) caching.
 */
@Service
public class ChatCompletionService {

    private final ProviderRouter providerRouter;
    private final ExactResponseCache exactResponseCache;
    private final SemanticResponseCache semanticResponseCache;
    private final OpenAiEmbeddingClient embeddingClient;

    /**
     * Creates the chat completion service.
     *
     * @param providerRouter         upstream router
     * @param exactResponseCache     Redis exact cache
     * @param semanticResponseCache  pgvector semantic cache
     * @param embeddingClient        OpenAI-compatible embedding client
     */
    public ChatCompletionService(
        ProviderRouter providerRouter,
        ExactResponseCache exactResponseCache,
        SemanticResponseCache semanticResponseCache,
        OpenAiEmbeddingClient embeddingClient
    ) {
        this.providerRouter = providerRouter;
        this.exactResponseCache = exactResponseCache;
        this.semanticResponseCache = semanticResponseCache;
        this.embeddingClient = embeddingClient;
    }

    /**
     * Executes a chat completion with caching layered ahead of provider routing.
     *
     * @param request canonical request
     * @return canonical response (possibly cached)
     */
    public ChatResponse complete(ChatRequest request) {
        long startNanos = System.nanoTime();

        Optional<ChatResponse> exactHit = exactResponseCache.getIfPresent(request);
        if (exactHit.isPresent()) {
            return exactHit.get().withFromCacheAndLatency(true, elapsedMillis(startNanos));
        }

        float[] embedding = null;
        if (semanticResponseCache.isActive()) {
            embedding = embeddingClient.embedOrNull(RequestCanonicalizer.promptForEmbedding(request));
            if (embedding != null) {
                Optional<ChatResponse> semanticHit = semanticResponseCache.lookup(request, embedding);
                if (semanticHit.isPresent()) {
                    return semanticHit.get().withFromCacheAndLatency(true, elapsedMillis(startNanos));
                }
            }
        }

        ChatResponse live = providerRouter.route(request);
        exactResponseCache.put(request, live);
        if (embedding != null) {
            semanticResponseCache.store(request, live, embedding);
        }
        return live;
    }

    private static long elapsedMillis(long startNanos) {
        return (System.nanoTime() - startNanos) / 1_000_000L;
    }
}
