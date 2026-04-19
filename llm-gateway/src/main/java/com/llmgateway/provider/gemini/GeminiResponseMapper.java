package com.llmgateway.provider.gemini;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.llmgateway.api.dto.ChatResponse;
import com.llmgateway.api.dto.Choice;
import com.llmgateway.api.dto.Usage;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Maps Gemini generateContent payloads into the gateway canonical response.
 */
@Component
class GeminiResponseMapper {

    /**
     * Converts a raw Gemini response into a {@link ChatResponse}.
     *
     * @param raw       parsed Gemini body
     * @param model     requested model id
     * @param latencyMs measured latency
     * @return canonical response
     */
    ChatResponse toCanonical(GeminiRawResponse raw, String model, long latencyMs) {
        String text = "";
        String finish = null;
        if (raw.candidates() != null && !raw.candidates().isEmpty()) {
            Candidate c = raw.candidates().getFirst();
            finish = c.finishReason();
            if (c.content() != null && c.content().parts() != null) {
                text = c.content().parts().stream()
                    .map(Part::text)
                    .filter(t -> t != null)
                    .reduce("", String::concat);
            }
        }
        UsageMeta meta = raw.usageMetadata();
        int prompt = meta != null ? meta.promptTokenCount() : 0;
        int completion = meta != null ? meta.candidatesTokenCount() : 0;
        int total = meta != null ? meta.totalTokenCount() : prompt + completion;
        return new ChatResponse(
            null,
            model,
            "gemini",
            new Choice("assistant", text, finish),
            new Usage(prompt, completion, total),
            false,
            latencyMs
        );
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    record GeminiRawResponse(
        List<Candidate> candidates,
        @JsonProperty("usageMetadata") UsageMeta usageMetadata
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    record Candidate(
        Content content,
        @JsonProperty("finishReason") String finishReason
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    record Content(
        List<Part> parts,
        String role
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    record Part(
        String text
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    record UsageMeta(
        @JsonProperty("promptTokenCount") int promptTokenCount,
        @JsonProperty("candidatesTokenCount") int candidatesTokenCount,
        @JsonProperty("totalTokenCount") int totalTokenCount
    ) {
    }
}
