package com.llmgateway.cache;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.llmgateway.config.CacheProperties;
import com.llmgateway.config.LlmProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Calls OpenAI-compatible {@code /v1/embeddings} to build vectors for semantic cache lookups.
 */
@Component
public class OpenAiEmbeddingClient {

    private static final Logger log = LoggerFactory.getLogger(OpenAiEmbeddingClient.class);
    private static final Duration TIMEOUT = Duration.ofSeconds(30);

    private final WebClient webClient;
    private final LlmProperties.OpenAi openAi;
    private final CacheProperties cacheProperties;

    /**
     * Creates the embedding client.
     *
     * @param llmProperties   provider configuration
     * @param cacheProperties cache configuration
     */
    public OpenAiEmbeddingClient(LlmProperties llmProperties, CacheProperties cacheProperties) {
        this.openAi = llmProperties.openai();
        this.cacheProperties = cacheProperties;
        this.webClient = WebClient.builder()
            .baseUrl(trimTrailingSlash(openAi.baseUrl()))
            .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
            .build();
    }

    /**
     * Returns an embedding vector for the given text, or {@code null} when semantic caching
     * cannot be performed (missing API key, disabled model, or upstream failure).
     *
     * @param input text to embed
     * @return embedding components, or null
     */
    public float[] embedOrNull(String input) {
        if (!StringUtils.hasText(openAi.apiKey()) || !StringUtils.hasText(input)) {
            return null;
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("model", cacheProperties.embeddingModel());
        body.put("input", input);
        try {
            EmbeddingResponse response = webClient.post()
                .uri("/v1/embeddings")
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + openAi.apiKey())
                .bodyValue(body)
                .retrieve()
                .bodyToMono(EmbeddingResponse.class)
                .block(TIMEOUT);
            if (response == null || response.data() == null || response.data().isEmpty()) {
                log.warn("OpenAI embeddings returned empty payload");
                return null;
            }
            List<Float> floats = response.data().getFirst().embedding();
            if (floats == null || floats.size() != 1536) {
                log.warn("OpenAI embeddings returned unexpected dimension: {}", floats == null ? null : floats.size());
                return null;
            }
            float[] out = new float[floats.size()];
            for (int i = 0; i < floats.size(); i++) {
                out[i] = floats.get(i);
            }
            return out;
        } catch (WebClientResponseException ex) {
            log.warn("OpenAI embeddings request failed: {}", ex.getStatusCode(), ex);
            return null;
        } catch (RuntimeException ex) {
            log.warn("OpenAI embeddings request failed", ex);
            return null;
        }
    }

    private static String trimTrailingSlash(String url) {
        if (url == null || url.isEmpty()) {
            return "";
        }
        return url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    private record EmbeddingResponse(
        List<Datum> data,
        String model
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    private record Datum(
        List<Float> embedding
    ) {
    }
}
