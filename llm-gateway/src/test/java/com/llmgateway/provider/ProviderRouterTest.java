package com.llmgateway.provider;

import com.llmgateway.api.dto.ChatRequest;
import com.llmgateway.api.dto.ChatResponse;
import com.llmgateway.api.dto.Choice;
import com.llmgateway.api.dto.Message;
import com.llmgateway.api.dto.Usage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link ProviderRouter}.
 */
@ExtendWith(MockitoExtension.class)
class ProviderRouterTest {

    @Mock
    private LlmProvider openai;

    @Mock
    private LlmProvider anthropic;

    @Mock
    private LlmProvider gemini;

    private ModelTranslator translator;
    private ProviderRouter router;

    /**
     * Wires default stubbing before each test.
     */
    @BeforeEach
    void setUp() {
        translator = new ModelTranslator();
        when(openai.name()).thenReturn("openai");
        when(anthropic.name()).thenReturn("anthropic");
        when(gemini.name()).thenReturn("gemini");
        router = new ProviderRouter(List.of(openai, anthropic, gemini), translator);
    }

    /**
     * Verifies the primary provider is used when healthy.
     */
    @Test
    void routesToPrimaryWhenHealthy() {
        ChatRequest req = new ChatRequest(
            "gpt-4o",
            List.of(new Message("user", "ping")),
            null,
            null,
            "u1"
        );
        when(openai.supportsModel("gpt-4o")).thenReturn(true);
        when(openai.isHealthy()).thenReturn(true);
        ChatResponse expected = sample("openai", "gpt-4o");
        when(openai.complete(req)).thenReturn(expected);

        ChatResponse actual = router.route(req);

        assertThat(actual).isEqualTo(expected);
        verify(openai).complete(req);
        verify(anthropic, never()).complete(any());
    }

    /**
     * Verifies failover invokes a secondary provider with a translated model.
     */
    @Test
    void failsOverWhenPrimaryUnhealthy() {
        ChatRequest req = new ChatRequest(
            "gpt-4o",
            List.of(new Message("user", "ping")),
            null,
            null,
            "u1"
        );
        when(anthropic.supportsModel("gpt-4o")).thenReturn(false);
        when(gemini.supportsModel("gpt-4o")).thenReturn(false);
        when(openai.supportsModel("gpt-4o")).thenReturn(true);
        when(openai.isHealthy()).thenReturn(false);
        when(anthropic.supportsModel("claude-3-5-sonnet-20241022")).thenReturn(true);
        when(anthropic.isHealthy()).thenReturn(true);
        ChatResponse expected = sample("anthropic", "claude-3-5-sonnet-20241022");
        when(anthropic.complete(any())).thenReturn(expected);

        ChatResponse actual = router.route(req);

        assertThat(actual).isEqualTo(expected);
        verify(anthropic).complete(any());
    }

    /**
     * Verifies unknown models surface a stable error.
     */
    @Test
    void rejectsUnknownModel() {
        ChatRequest req = new ChatRequest(
            "unknown-model",
            List.of(new Message("user", "ping")),
            null,
            null,
            "u1"
        );
        assertThatThrownBy(() -> router.route(req))
            .isInstanceOf(ProviderException.class)
            .hasFieldOrPropertyWithValue("code", "model.unsupported");
    }

    private static ChatResponse sample(String provider, String model) {
        return new ChatResponse(
            "id-1",
            model,
            provider,
            new Choice("assistant", "ok", "stop"),
            new Usage(1, 1, 2),
            false,
            12L
        );
    }
}
