package com.llmgateway.provider.anthropic;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.llmgateway.api.dto.ChatResponse;
import com.llmgateway.api.dto.Choice;
import com.llmgateway.api.dto.Usage;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.stream.Collectors;

/**
 * Maps Anthropic Messages API payloads into the gateway canonical response.
 */
@Component
class AnthropicResponseMapper {

    /**
     * Converts a raw Anthropic response into a {@link ChatResponse}.
     *
     * @param raw       parsed Anthropic body
     * @param model     requested model id
     * @param latencyMs measured latency
     * @return canonical response
     */
    ChatResponse toCanonical(AnthropicRawResponse raw, String model, long latencyMs) {
        String text = "";
        if (raw.content() != null) {
            text = raw.content().stream()
                .filter(c -> "text".equalsIgnoreCase(c.type()))
                .map(ContentBlock::text)
                .collect(Collectors.joining());
        }
        Choice choice = new Choice("assistant", text, raw.stopReason());
        UsageRaw u = raw.usage();
        int prompt = u != null ? u.inputTokens() : 0;
        int completion = u != null ? u.outputTokens() : 0;
        return new ChatResponse(
            raw.id(),
            raw.model() != null ? raw.model() : model,
            "anthropic",
            choice,
            new Usage(prompt, completion, prompt + completion),
            false,
            latencyMs
        );
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    record AnthropicRawResponse(
        String id,
        String model,
        List<ContentBlock> content,
        @JsonProperty("stop_reason") String stopReason,
        UsageRaw usage
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    record ContentBlock(
        String type,
        String text
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    record UsageRaw(
        @JsonProperty("input_tokens") int inputTokens,
        @JsonProperty("output_tokens") int outputTokens
    ) {
    }
}
