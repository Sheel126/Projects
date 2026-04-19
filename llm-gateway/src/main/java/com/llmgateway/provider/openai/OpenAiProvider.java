package com.llmgateway.provider.openai;

import com.llmgateway.api.dto.ChatRequest;
import com.llmgateway.api.dto.ChatResponse;
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
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * OpenAI Chat Completions adapter.
 */
@Component
public class OpenAiProvider implements LlmProvider {

    private static final Duration TIMEOUT = Duration.ofMinutes(2);

    private final WebClient webClient;
    private final LlmProperties.OpenAi props;
    private final OpenAiResponseMapper mapper;

    /**
     * Constructs the OpenAI provider adapter.
     *
     * @param props  OpenAI configuration
     * @param mapper response mapper
     */
    public OpenAiProvider(LlmProperties props, OpenAiResponseMapper mapper) {
        this.props = props.openai();
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
        return "openai";
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
        String m = model.toLowerCase();
        return m.startsWith("gpt-") || m.startsWith("o1") || m.startsWith("o3") || m.startsWith("ft:");
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public ChatResponse complete(ChatRequest request) {
        long start = System.nanoTime();
        try {
            OpenAiResponseMapper.OpenAiRawResponse raw = webClient.post()
                .uri("/v1/chat/completions")
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + props.apiKey())
                .bodyValue(buildBody(request))
                .retrieve()
                .bodyToMono(OpenAiResponseMapper.OpenAiRawResponse.class)
                .block(TIMEOUT);
            if (raw == null) {
                throw new ProviderException("openai.empty", "Empty response from OpenAI");
            }
            long ms = (System.nanoTime() - start) / 1_000_000L;
            return mapper.toCanonical(raw, request.model(), ms);
        } catch (WebClientResponseException ex) {
            throw new ProviderException(
                "openai.http",
                "OpenAI request failed: " + ex.getStatusCode(),
                ex
            );
        }
    }

    private static Map<String, Object> buildBody(ChatRequest request) {
        List<Map<String, String>> msgs = request.messages().stream()
            .map(m -> Map.of("role", m.role(), "content", m.content()))
            .toList();
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("model", request.model());
        body.put("messages", msgs);
        if (request.temperature() != null) {
            body.put("temperature", request.temperature());
        }
        if (request.maxTokens() != null) {
            body.put("max_tokens", request.maxTokens());
        }
        return body;
    }

    private static String trimTrailingSlash(String url) {
        if (url == null || url.isEmpty()) {
            return "";
        }
        return url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
    }
}
