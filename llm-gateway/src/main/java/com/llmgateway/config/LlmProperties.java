package com.llmgateway.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Externalized configuration for upstream LLM providers.
 *
 * @param openai     OpenAI connectivity
 * @param anthropic  Anthropic connectivity
 * @param gemini     Google Gemini connectivity
 */
@ConfigurationProperties(prefix = "llm")
public record LlmProperties(
    OpenAi openai,
    Anthropic anthropic,
    Gemini gemini
) {

    /**
     * OpenAI-specific settings.
     *
     * @param baseUrl API base URL without trailing slash
     * @param apiKey  bearer token value
     */
    public record OpenAi(String baseUrl, String apiKey) {
    }

    /**
     * Anthropic-specific settings.
     *
     * @param baseUrl API base URL without trailing slash
     * @param apiKey  API key header value
     * @param version anthropic-version header value
     */
    public record Anthropic(String baseUrl, String apiKey, String version) {
    }

    /**
     * Gemini-specific settings.
     *
     * @param baseUrl API base URL without trailing slash
     * @param apiKey  API key query parameter value
     */
    public record Gemini(String baseUrl, String apiKey) {
    }
}
