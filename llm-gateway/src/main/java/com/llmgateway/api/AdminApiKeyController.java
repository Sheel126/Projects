package com.llmgateway.api;

import com.llmgateway.config.GatewaySecurityProperties;
import com.llmgateway.security.ApiKeyService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import org.springframework.http.ResponseEntity;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
@RequestMapping("/v1/admin")
public class AdminApiKeyController {

    private final ApiKeyService apiKeyService;
    private final GatewaySecurityProperties props;

    public AdminApiKeyController(ApiKeyService apiKeyService, GatewaySecurityProperties props) {
        this.apiKeyService = apiKeyService;
        this.props = props;
    }

    @PostMapping("/api-keys")
    public ResponseEntity<CreateApiKeyResponse> create(
        @RequestHeader(name = "X-Admin-Token", required = false) String adminToken,
        @Valid @RequestBody CreateApiKeyRequest request
    ) {
        requireAdmin(adminToken);
        ApiKeyService.CreateApiKeyResult created = apiKeyService.create(
            request.name(),
            request.userId(),
            request.rateLimitRpm()
        );
        return ResponseEntity.ok(new CreateApiKeyResponse(created.id(), created.apiKey()));
    }

    @DeleteMapping("/api-keys/{id}")
    public ResponseEntity<Void> revoke(
        @RequestHeader(name = "X-Admin-Token", required = false) String adminToken,
        @PathVariable("id") UUID id
    ) {
        requireAdmin(adminToken);
        apiKeyService.revoke(id);
        return ResponseEntity.noContent().build();
    }

    private void requireAdmin(String token) {
        String expected = props.auth().adminToken();
        if (!StringUtils.hasText(expected) || token == null || !expected.equals(token)) {
            throw new AuthException("auth.admin", "Missing or invalid admin token");
        }
    }

    public record CreateApiKeyRequest(
        @NotBlank String name,
        @NotBlank String userId,
        Integer rateLimitRpm
    ) {
    }

    public record CreateApiKeyResponse(
        @NotNull UUID id,
        @NotBlank String apiKey
    ) {
    }
}

