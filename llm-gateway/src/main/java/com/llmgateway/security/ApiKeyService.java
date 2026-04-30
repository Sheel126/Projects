package com.llmgateway.security;

import com.llmgateway.config.GatewaySecurityProperties;
import org.springframework.stereotype.Service;

import java.security.SecureRandom;
import java.util.Base64;
import java.util.Optional;
import java.util.UUID;

@Service
public class ApiKeyService {

    private static final SecureRandom rng = new SecureRandom();

    private final ApiKeyRepository repo;
    private final GatewaySecurityProperties props;

    public ApiKeyService(ApiKeyRepository repo, GatewaySecurityProperties props) {
        this.repo = repo;
        this.props = props;
    }

    public Optional<ApiKeyPrincipal> authenticate(String rawApiKey) {
        if (rawApiKey == null || rawApiKey.isBlank()) {
            return Optional.empty();
        }
        String hash = ApiKeyHasher.hmacSha256Hex(props.auth().hmacSecret(), rawApiKey.trim());
        return repo.findActiveByHash(hash);
    }

    public CreateApiKeyResult create(String name, String userId, Integer rateLimitRpm) {
        String raw = generateRawKey();
        String hash = ApiKeyHasher.hmacSha256Hex(props.auth().hmacSecret(), raw);
        UUID id = repo.insert(hash, name, userId, rateLimitRpm);
        return new CreateApiKeyResult(id, raw);
    }

    public int revoke(UUID id) {
        return repo.revoke(id);
    }

    private static String generateRawKey() {
        byte[] bytes = new byte[32];
        rng.nextBytes(bytes);
        return "lgw_" + Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    public record CreateApiKeyResult(UUID id, String apiKey) {
    }
}

