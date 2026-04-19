package com.llmgateway.provider.anthropic;

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
import java.util.stream.Collectors;

/**
 * Anthropic Messages API adapter.
 */
@Component
public class AnthropicProvider implements LlmProvider {

    private static final Duration TIMEOUT = Duration.ofMinutes(2);
    private static final String ANTHROPIC_VERSION_HEADER = "anthropic-version";

    private final WebClient webClient;
    private final LlmProperties.Anthropic props;
    private final AnthropicResponseMapper mapper;

    /**
     * Constructs the Anthropic provider adapter.
     *
     * @param props  gateway LLM properties
     * @param mapper response mapper
     */
    public AnthropicProvider(LlmProperties props, AnthropicResponseMapper mapper) {
        this.props = props.anthropic();
        this.mapper = mapper;
        this.webClient = WebClient.builder()
            .baseUrl(trimTrailingSlash(this.props.baseUrl()))
            .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
            .defaultHeader("x-api-key", this.props.apiKey())
            .defaultHeader(ANTHROPIC_VERSION_HEADER, this.props.version())
            .build();
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public String name() {
        return "anthropic";
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
        return model.toLowerCase().startsWith("claude-");
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public ChatResponse complete(ChatRequest request) {
        long start = System.nanoTime();
        try {
            AnthropicResponseMapper.AnthropicRawResponse raw = webClient.post()
                .uri("/v1/messages")
                .bodyValue(buildBody(request))
                .retrieve()
                .bodyToMono(AnthropicResponseMapper.AnthropicRawResponse.class)
                .block(TIMEOUT);
            if (raw == null) {
                throw new ProviderException("anthropic.empty", "Empty response from Anthropic");
            }
            long ms = (System.nanoTime() - start) / 1_000_000L;
            return mapper.toCanonical(raw, request.model(), ms);
        } catch (WebClientResponseException ex) {
            throw new ProviderException(
                "anthropic.http",
                "Anthropic request failed: " + ex.getStatusCode(),
                ex
            );
        }
    }

    private Map<String, Object> buildBody(ChatRequest request) {
        List<Message> messages = request.messages();
        String system = messages.stream()
            .filter(m -> "system".equalsIgnoreCase(m.role()))
            .map(Message::content)
            .collect(Collectors.joining("\n"));

        List<Map<String, Object>> apiMessages = new ArrayList<>();
        for (Message m : messages) {
            if ("system".equalsIgnoreCase(m.role())) {
                continue;
            }
            String role = "assistant".equalsIgnoreCase(m.role()) ? "assistant" : "user";
            apiMessages.add(Map.of(
                "role", role,
                "content", List.of(Map.of("type", "text", "text", m.content()))
            ));
        }

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("model", request.model());
        body.put("max_tokens", request.maxTokens() != null ? request.maxTokens() : 1024);
        if (StringUtils.hasText(system)) {
            body.put("system", system);
        }
        body.put("messages", apiMessages);
        if (request.temperature() != null) {
            body.put("temperature", request.temperature());
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
