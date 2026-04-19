package com.llmgateway.provider;

import com.llmgateway.api.dto.ChatRequest;
import com.llmgateway.api.dto.ChatResponse;

/**
 * Adapter interface for all LLM providers.
 * Each provider translates to/from the gateway's canonical request/response format.
 */
public interface LlmProvider {

    /**
     * Returns the provider identifier (e.g. "openai", "anthropic", "gemini").
     *
     * @return stable provider id
     */
    String name();

    /**
     * Sends a chat completion request to the underlying provider.
     *
     * @param request canonical gateway request
     * @return canonical gateway response
     * @throws ProviderException on upstream errors
     */
    ChatResponse complete(ChatRequest request);

    /**
     * Returns whether this provider is currently available.
     * Used by the router for health-based routing decisions.
     *
     * @return true if the provider can accept traffic
     */
    boolean isHealthy();

    /**
     * Returns true if this provider natively supports the requested model id.
     *
     * @param model model name from the caller
     * @return true when this provider should be primary for the model
     */
    boolean supportsModel(String model);
}
