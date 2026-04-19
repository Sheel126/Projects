package com.llmgateway.integration;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.github.tomakehurst.wiremock.WireMockServer;
import com.llmgateway.api.dto.ChatRequest;
import com.llmgateway.api.dto.Message;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.util.List;

import static com.github.tomakehurst.wiremock.client.WireMock.aResponse;
import static com.github.tomakehurst.wiremock.client.WireMock.post;
import static com.github.tomakehurst.wiremock.client.WireMock.urlPathMatching;
import static com.github.tomakehurst.wiremock.core.WireMockConfiguration.wireMockConfig;
import static org.assertj.core.api.Assertions.assertThat;

/**
 * End-to-end tests that exercise provider routing against WireMock stubs with real infrastructure.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers(disabledWithoutDocker = true)
class ChatCompletionIntegrationTest {

    private static WireMockServer wireMock;

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

    @LocalServerPort
    private int port;

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    /**
     * Stops WireMock after the test class completes.
     */
    @AfterAll
    static void stopWireMock() {
        if (wireMock != null) {
            wireMock.stop();
            wireMock = null;
        }
    }

    /**
     * Binds container endpoints and provider base URLs for the Spring context.
     *
     * @param registry Spring dynamic property registry
     */
    @DynamicPropertySource
    static void registerProps(DynamicPropertyRegistry registry) {
        startWireMockIfNeeded();
        String base = "http://localhost:" + wireMock.port();
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
        registry.add(
            "spring.data.redis.url",
            () -> "redis://" + REDIS.getHost() + ":" + REDIS.getMappedPort(6379)
        );
        registry.add("llm.openai.base-url", () -> base);
        registry.add("llm.openai.api-key", () -> "sk-test");
        registry.add("llm.anthropic.base-url", () -> base);
        registry.add("llm.anthropic.api-key", () -> "sk-ant-test");
        registry.add("llm.anthropic.version", () -> "2023-06-01");
        registry.add("llm.gemini.base-url", () -> base);
        registry.add("llm.gemini.api-key", () -> "gemini-test");
    }

    private static synchronized void startWireMockIfNeeded() {
        if (wireMock != null) {
            return;
        }
        wireMock = new WireMockServer(wireMockConfig().dynamicPort());
        wireMock.start();
        wireMock.stubFor(post("/v1/chat/completions")
            .willReturn(aResponse()
                .withStatus(200)
                .withHeader("Content-Type", "application/json")
                .withBody(
                    """
                    {
                      "id": "chatcmpl-test",
                      "model": "gpt-4o",
                      "choices": [{
                        "message": {"role": "assistant", "content": "openai-ok"},
                        "finish_reason": "stop"
                      }],
                      "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}
                    }
                    """
                )));
        wireMock.stubFor(post("/v1/messages")
            .willReturn(aResponse()
                .withStatus(200)
                .withHeader("Content-Type", "application/json")
                .withBody(
                    """
                    {
                      "id": "msg_test",
                      "model": "claude-3-5-sonnet-20241022",
                      "content": [{"type": "text", "text": "anthropic-ok"}],
                      "stop_reason": "end_turn",
                      "usage": {"input_tokens": 2, "output_tokens": 5}
                    }
                    """
                )));
        wireMock.stubFor(post(urlPathMatching("/v1beta/models/gemini-1.5-pro:generateContent"))
            .willReturn(aResponse()
                .withStatus(200)
                .withHeader("Content-Type", "application/json")
                .withBody(
                    """
                    {
                      "candidates": [{
                        "content": {"parts": [{"text": "gemini-ok"}], "role": "model"},
                        "finishReason": "STOP"
                      }],
                      "usageMetadata": {
                        "promptTokenCount": 1,
                        "candidatesTokenCount": 2,
                        "totalTokenCount": 3
                      }
                    }
                    """
                )));
    }

    /**
     * Proxies an OpenAI model through WireMock.
     */
    @Test
    void openAiCompletion() throws Exception {
        ChatRequest body = new ChatRequest(
            "gpt-4o",
            List.of(new Message("user", "hi")),
            0.2,
            32,
            "integration-user"
        );
        ResponseEntity<String> res = restTemplate.postForEntity(
            "http://localhost:" + port + "/v1/chat/completions",
            body,
            String.class
        );
        assertThat(res.getStatusCode()).isEqualTo(HttpStatus.OK);
        JsonNode root = objectMapper.readTree(res.getBody());
        assertThat(root.path("provider").asText()).isEqualTo("openai");
        assertThat(root.path("choice").path("content").asText()).isEqualTo("openai-ok");
    }

    /**
     * Proxies an Anthropic model through WireMock.
     */
    @Test
    void anthropicCompletion() throws Exception {
        ChatRequest body = new ChatRequest(
            "claude-3-5-sonnet-20241022",
            List.of(new Message("user", "hi")),
            null,
            64,
            "integration-user"
        );
        ResponseEntity<String> res = restTemplate.postForEntity(
            "http://localhost:" + port + "/v1/chat/completions",
            body,
            String.class
        );
        assertThat(res.getStatusCode()).isEqualTo(HttpStatus.OK);
        JsonNode root = objectMapper.readTree(res.getBody());
        assertThat(root.path("provider").asText()).isEqualTo("anthropic");
        assertThat(root.path("choice").path("content").asText()).isEqualTo("anthropic-ok");
    }

    /**
     * Proxies a Gemini model through WireMock.
     */
    @Test
    void geminiCompletion() throws Exception {
        ChatRequest body = new ChatRequest(
            "gemini-1.5-pro",
            List.of(new Message("user", "hi")),
            null,
            32,
            "integration-user"
        );
        ResponseEntity<String> res = restTemplate.postForEntity(
            "http://localhost:" + port + "/v1/chat/completions",
            body,
            String.class
        );
        assertThat(res.getStatusCode()).isEqualTo(HttpStatus.OK);
        JsonNode root = objectMapper.readTree(res.getBody());
        assertThat(root.path("provider").asText()).isEqualTo("gemini");
        assertThat(root.path("choice").path("content").asText()).isEqualTo("gemini-ok");
    }

    /**
     * Verifies the liveness endpoint is reachable.
     */
    @Test
    void healthEndpoint() {
        ResponseEntity<Void> res = restTemplate.getForEntity(
            "http://localhost:" + port + "/health",
            Void.class
        );
        assertThat(res.getStatusCode()).isEqualTo(HttpStatus.OK);
    }
}
