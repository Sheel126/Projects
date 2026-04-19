package com.sheel.finance_ai.ai.prompt;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

import org.springframework.core.io.ClassPathResource;
import org.springframework.util.StreamUtils;

public final class PromptLoader {

    private PromptLoader() {}

    public static String load(String path) {
        try {
            ClassPathResource resource = new ClassPathResource(path);
            return StreamUtils.copyToString(
                resource.getInputStream(),
                StandardCharsets.UTF_8
            );
        } catch (IOException e) {
            throw new RuntimeException("Failed to load prompt: " + path, e);
        }
    }
}
