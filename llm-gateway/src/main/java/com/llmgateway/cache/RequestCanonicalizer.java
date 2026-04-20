package com.llmgateway.cache;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.llmgateway.api.dto.ChatRequest;
import com.llmgateway.api.dto.Message;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Stable serialization and hashing for cache keys.
 */
public final class RequestCanonicalizer {

    private RequestCanonicalizer() {
    }

    /**
     * Builds a deterministic JSON representation of the request fields that must
     * participate in exact de-duplication.
     *
     * @param mapper JSON mapper
     * @param request incoming request
     * @return canonical JSON string
     */
    public static String canonicalJson(ObjectMapper mapper, ChatRequest request) throws JsonProcessingException {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("model", request.model());
        List<Map<String, String>> messages = request.messages().stream()
            .map(m -> Map.of("role", m.role(), "content", m.content()))
            .toList();
        map.put("messages", messages);
        if (request.temperature() != null) {
            map.put("temperature", request.temperature());
        }
        if (request.maxTokens() != null) {
            map.put("maxTokens", request.maxTokens());
        }
        if (request.userId() != null) {
            map.put("userId", request.userId());
        }
        return mapper.writeValueAsString(map);
    }

    /**
     * SHA-256 hex digest of {@link #canonicalJson(ObjectMapper, ChatRequest)}.
     *
     * @param mapper JSON mapper
     * @param request incoming request
     * @return hex digest
     */
    public static String sha256Hex(ObjectMapper mapper, ChatRequest request) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                .digest(canonicalJson(mapper, request).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException | JsonProcessingException e) {
            throw new IllegalStateException("Unable to hash chat request", e);
        }
    }

    /**
     * Text used for embedding generation and {@link #promptHash(ChatRequest)}.
     *
     * @param request incoming request
     * @return normalized prompt text
     */
    public static String promptForEmbedding(ChatRequest request) {
        StringBuilder sb = new StringBuilder();
        for (Message m : request.messages()) {
            sb.append(m.role()).append(": ").append(m.content()).append('\n');
        }
        sb.append("model: ").append(request.model());
        return sb.toString();
    }

    /**
     * SHA-256 hex digest of {@link #promptForEmbedding(ChatRequest)}.
     *
     * @param request incoming request
     * @return hex digest
     */
    public static String promptHash(ChatRequest request) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                .digest(promptForEmbedding(request).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("Unable to hash prompt", e);
        }
    }
}
