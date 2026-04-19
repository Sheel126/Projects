package com.llmgateway.provider.gemini;

import com.llmgateway.api.dto.ChatRequest;
import com.llmgateway.api.dto.ChatResponse;
import com.llmgateway.api.dto.Message;
import com.llmgateway.config.LlmProperties;
import com.llmgateway.provider.LlmProvider;
import com.llmgateway.provider.ProviderException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Google Gemini generateContent adapter.
 */
@Component
public class GeminiProvider implements LlmProvider {

    private static final Duration TIMEOUT = Duration.ofMinutes(2);

    private final WebClient webClient;
    private final LlmProperties.Gemini props;
    private final GeminiResponseMapper mapper;

    /**
     * Constructs the Gemini provider adapter.
     *
     * @param props  gateway LLM properties
     * @param mapper response mapper
     */
    public GeminiProvider(LlmProperties props, GeminiResponseMapper mapper) {
        this.props = props.gemini();
        this.mapper = mapper;
        this.webClient = WebClient.builder()
            .baseUrl(trimTrailingSlash(this.props.baseUrl()))
            .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
            .build();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public String name() {
        return "gemini";
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean isHealthy() {
        return StringUtils.hasText(props.apiKey());
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean supportsModel(String model) {
        if (!StringUtils.hasText(model)) {
            return false;
        }
        return model.toLowerCase().startsWith("gemini-");
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public ChatResponse complete(ChatRequest request) {
        long start = System.nanoTime();
        try {
            GeminiResponseMapper.GeminiRawResponse raw = webClient.post()
                .uri(uriBuilder -> uriBuilder
                    .path("/v1beta/models/{model}:generateContent")
                    .queryParam("key", props.apiKey())
                    .build(request.model()))
                .bodyValue(buildBody(request))
                .retrieve()
                .bodyToMono(GeminiResponseMapper.GeminiRawResponse.class)
                .block(TIMEOUT);
            if (raw == null) {
                throw new ProviderException("gemini.empty", "Empty response from Gemini");
            }
            long ms = (System.nanoTime() - start) / 1_000_000L;
            return mapper.toCanonical(raw, request.model(), ms);
        } catch (WebClientResponseException ex) {
            throw new ProviderException(
                "gemini.http",
                "Gemini request failed: " + ex.getStatusCode(),
                ex
            );
        }
    }

    private static Map<String, Object> buildBody(ChatRequest request) {
        List<Map<String, Object>> contents = new ArrayList<>();
        for (Message m : request.messages()) {
            String role = mapRole(m.role());
            contents.add(Map.of(
                "role", role,
                "parts", List.of(Map.of("text", m.content()))
            ));
        }
        Map<String, Object> generationConfig = new LinkedHashMap<>();
        if (request.temperature() != null) {
            generationConfig.put("temperature", request.temperature());
        }
        if (request.maxTokens() != null) {
            generationConfig.put("maxOutputTokens", request.maxTokens());
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("contents", contents);
        if (!generationConfig.isEmpty()) {
            body.put("generationConfig", generationConfig);
        }
        return body;
    }

    private static String mapRole(String role) {
        if ("assistant".equalsIgnoreCase(role)) {
            return "model";
        }
        if ("system".equalsIgnoreCase(role)) {
            return "user";
        }
        return "user";
    }

    private static String trimTrailingSlash(String url) {
        if (url == null || url.isEmpty()) {
            return "";
        }
        return url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
    }
}
