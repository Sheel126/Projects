package com.llmgateway.integration;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers(disabledWithoutDocker = true)
class AuthRateLimitIntegrationTest {

    @Container
    private static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>(
        DockerImageName.parse("pgvector/pgvector:pg16")
    )
        .withDatabaseName("llmgateway")
        .withUsername("gateway")
        .withPassword("test");

    @Container
    private static final GenericContainer<?> REDIS = new GenericContainer<>(
        DockerImageName.parse("redis:7-alpine")
    ).withExposedPorts(6379);

    @DynamicPropertySource
    static void registerProps(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        registry.add(
            "spring.data.redis.url",
            () -> "redis://" + REDIS.getHost() + ":" + REDIS.getMappedPort(6379)
        );

        registry.add("gateway.security.auth.enabled", () -> "true");
        registry.add("gateway.security.auth.header-name", () -> "X-API-Key");
        registry.add("gateway.security.auth.hmac-secret", () -> "test-hmac-secret");
        registry.add("gateway.security.auth.admin-token", () -> "test-admin-token");

        registry.add("gateway.security.rate-limit.enabled", () -> "true");
        registry.add("gateway.security.rate-limit.default-rpm", () -> "2");
        registry.add("gateway.security.rate-limit.window-seconds", () -> "60");
    }

    @LocalServerPort
    private int port;

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void apiKeyAuthAndSlidingWindowRateLimit() throws Exception {
        String apiKey = createApiKey("demo", "user-1", 2);

        // First request allowed
        ResponseEntity<String> who1 = whoami(apiKey);
        assertThat(who1.getStatusCode()).isEqualTo(HttpStatus.OK);
        JsonNode body1 = objectMapper.readTree(who1.getBody());
        assertThat(body1.path("apiKeyId").asText()).isNotBlank();
        assertThat(body1.path("userId").asText()).isEqualTo("user-1");

        // Second request allowed
        ResponseEntity<String> who2 = whoami(apiKey);
        assertThat(who2.getStatusCode()).isEqualTo(HttpStatus.OK);

        // Third request blocked by sliding window
        ResponseEntity<String> who3 = whoami(apiKey);
        assertThat(who3.getStatusCode().value()).isEqualTo(429);
        assertThat(who3.getHeaders().getFirst("Retry-After")).isNotBlank();
        JsonNode err = objectMapper.readTree(who3.getBody());
        assertThat(err.path("code").asText()).isEqualTo("ratelimit.exceeded");
    }

    private String createApiKey(String name, String userId, int rpm) throws Exception {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("X-Admin-Token", "test-admin-token");

        String json = """
            {"name":"%s","userId":"%s","rateLimitRpm":%d}
            """.formatted(name, userId, rpm);

        ResponseEntity<String> res = restTemplate.exchange(
            "http://localhost:" + port + "/v1/admin/api-keys",
            HttpMethod.POST,
            new HttpEntity<>(json, headers),
            String.class
        );
        assertThat(res.getStatusCode()).isEqualTo(HttpStatus.OK);
        JsonNode root = objectMapper.readTree(res.getBody());
        assertThat(root.path("apiKey").asText()).startsWith("lgw_");
        return root.path("apiKey").asText();
    }

    private ResponseEntity<String> whoami(String apiKey) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-API-Key", apiKey);
        return restTemplate.exchange(
            "http://localhost:" + port + "/v1/whoami",
            HttpMethod.GET,
            new HttpEntity<>(null, headers),
            String.class
        );
    }
}

