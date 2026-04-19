package com.llmgateway.api;

import com.llmgateway.api.dto.ChatRequest;
import com.llmgateway.api.dto.ChatResponse;
import com.llmgateway.provider.ProviderRouter;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

/**
 * REST controller exposing the unified chat completion API.
 */
@RestController
@RequestMapping("/v1")
public class ChatController {

    private final ProviderRouter router;

    /**
     * Creates the chat controller.
     *
     * @param router provider router
     */
    public ChatController(ProviderRouter router) {
        this.router = router;
    }

    /**
     * Unified chat completion endpoint.
     * Accepts requests in the gateway's canonical format and routes to the
     * appropriate provider based on the requested model.
     *
     * @param request  validated chat request body
     * @param apiKeyId optional authenticated API key id when auth is enabled
     * @return proxied completion from the selected provider
     */
    @PostMapping("/chat/completions")
    @SuppressWarnings("unused")
    public ResponseEntity<ChatResponse> complete(
        @Valid @RequestBody ChatRequest request,
        @RequestAttribute(name = "apiKeyId", required = false) UUID apiKeyId
    ) {
        ChatResponse response = router.route(request);
        return ResponseEntity.ok(response);
    }
}
