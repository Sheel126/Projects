package com.llmgateway.api;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
@RequestMapping("/v1")
public class WhoAmIController {

    @GetMapping("/whoami")
    public ResponseEntity<WhoAmIResponse> whoami(
        @RequestAttribute(name = "apiKeyId", required = false) UUID apiKeyId,
        @RequestAttribute(name = "userId", required = false) String userId
    ) {
        return ResponseEntity.ok(new WhoAmIResponse(apiKeyId, userId));
    }

    public record WhoAmIResponse(UUID apiKeyId, String userId) {
    }
}

