package com.llmgateway.api;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Exposes a simple liveness endpoint for load balancers and compose health checks.
 */
@RestController
public class LivenessController {

    /**
     * Returns HTTP 200 when the process is running.
     *
     * @return empty200 response
     */
    @GetMapping("/health")
    public ResponseEntity<Void> health() {
        return ResponseEntity.ok().build();
    }
}
