package com.llmgateway.security;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;

final class ApiKeyHasher {

    private ApiKeyHasher() {
    }

    static String hmacSha256Hex(String secret, String rawApiKey) {
        if (secret == null || secret.isBlank()) {
            throw new IllegalStateException("GATEWAY_API_KEY_HMAC_SECRET must be set when auth is enabled");
        }
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] bytes = mac.doFinal(rawApiKey.getBytes(StandardCharsets.UTF_8));
            return toHex(bytes);
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to hash API key", ex);
        }
    }

    private static String toHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }
}

