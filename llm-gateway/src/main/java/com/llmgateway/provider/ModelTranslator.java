package com.llmgateway.provider;

import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.Optional;

/**
 * Maps model names across providers for basic failover without caller changes.
 */
@Component
public class ModelTranslator {

    private static final Map<String, String> TO_ANTHROPIC = Map.of(
        "gpt-4o", "claude-3-5-sonnet-20241022",
        "gpt-4o-mini", "claude-3-5-haiku-20241022"
    );

    private static final Map<String, String> TO_OPENAI = Map.of(
        "claude-3-5-sonnet-20241022", "gpt-4o",
        "claude-3-5-haiku-20241022", "gpt-4o-mini"
    );

    private static final Map<String, String> TO_GEMINI = Map.of(
        "gpt-4o", "gemini-1.5-pro",
        "gpt-4o-mini", "gemini-1.5-flash",
        "claude-3-5-sonnet-20241022", "gemini-1.5-pro",
        "claude-3-5-haiku-20241022", "gemini-1.5-flash"
    );

    /**
     * Translates a model for the target provider when failing over from another vendor.
     *
     * @param targetProvider destination provider id
     * @param sourceModel    model requested by the caller
     * @return translated model if a mapping exists
     */
    public Optional<String> translateForProvider(String targetProvider, String sourceModel) {
        return switch (targetProvider) {
            case "anthropic" -> Optional.ofNullable(TO_ANTHROPIC.get(sourceModel));
            case "openai" -> Optional.ofNullable(TO_OPENAI.get(sourceModel));
            case "gemini" -> Optional.ofNullable(TO_GEMINI.get(sourceModel));
            default -> Optional.empty();
        };
    }
}
