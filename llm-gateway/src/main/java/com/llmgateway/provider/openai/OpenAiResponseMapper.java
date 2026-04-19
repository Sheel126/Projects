package com.llmgateway.provider.openai;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.llmgateway.api.dto.ChatResponse;
import com.llmgateway.api.dto.Choice;
import com.llmgateway.api.dto.Usage;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Maps OpenAI chat completion payloads into the gateway canonical response.
 */
@Component
class OpenAiResponseMapper {

    /**
     * Converts a raw OpenAI completion into a {@link ChatResponse}.
     *
     * @param raw       parsed OpenAI body
     * @param model     model that was requested
     * @param latencyMs measured latency
     * @return canonical response
     */
    ChatResponse toCanonical(OpenAiRawResponse raw, String model, long latencyMs) {
        if (raw.choices() == null || raw.choices().isEmpty()) {
            throw new IllegalArgumentException("OpenAI response missing choices");
        }
        ChoiceRaw first = raw.choices().getFirst();
        MessageRaw msg = first.message();
        Choice choice = new Choice(
            msg != null ? msg.role() : "assistant",
            msg != null ? msg.content() : "",
            first.finishReason()
        );
        UsageRaw u = raw.usage();
        int prompt = u != null ? u.promptTokens() : 0;
        int completion = u != null ? u.completionTokens() : 0;
        int total = u != null ? u.totalTokens() : prompt + completion;
        return new ChatResponse(
            raw.id(),
            raw.model() != null ? raw.model() : model,
            "openai",
            choice,
            new Usage(prompt, completion, total),
            false,
            latencyMs
        );
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    record OpenAiRawResponse(
        String id,
        String model,
        List<ChoiceRaw> choices,
        UsageRaw usage
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    record ChoiceRaw(
        MessageRaw message,
        @JsonProperty("finish_reason") String finishReason
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    record MessageRaw(
        String role,
        String content
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    record UsageRaw(
        @JsonProperty("prompt_tokens") int promptTokens,
        @JsonProperty("completion_tokens") int completionTokens,
        @JsonProperty("total_tokens") int totalTokens
    ) {
    }
}
