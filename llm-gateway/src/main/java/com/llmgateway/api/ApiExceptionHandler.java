package com.llmgateway.api;

import com.llmgateway.api.dto.ErrorResponse;
import com.llmgateway.provider.ProviderException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * Maps application exceptions to HTTP responses with stable error bodies.
 */
@RestControllerAdvice
public class ApiExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    /**
     * Handles upstream provider failures.
     *
     * @param ex provider exception
     * @return 502 response with error envelope
     */
    @ExceptionHandler(ProviderException.class)
    public ResponseEntity<ErrorResponse> onProvider(ProviderException ex) {
        log.warn("provider_error code={} message={}", ex.getCode(), ex.getMessage());
        return ResponseEntity
            .status(HttpStatus.BAD_GATEWAY)
            .body(new ErrorResponse(ex.getCode(), ex.getMessage()));
    }

    /**
     * Handles request validation failures.
     *
     * @param ex validation exception
     * @return 400 response
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> onValidation(MethodArgumentNotValidException ex) {
        String msg = ex.getBindingResult().getFieldErrors().stream()
            .map(e -> e.getField() + ": " + e.getDefaultMessage())
            .findFirst()
            .orElse("validation_failed");
        return ResponseEntity
            .status(HttpStatus.BAD_REQUEST)
            .body(new ErrorResponse("validation.failed", msg));
    }

    @ExceptionHandler(AuthException.class)
    public ResponseEntity<ErrorResponse> onAuth(AuthException ex) {
        return ResponseEntity
            .status(HttpStatus.UNAUTHORIZED)
            .body(new ErrorResponse(ex.getCode(), ex.getMessage()));
    }

    @ExceptionHandler(RateLimitException.class)
    public ResponseEntity<ErrorResponse> onRateLimit(RateLimitException ex) {
        return ResponseEntity
            .status(429)
            .header("Retry-After", Long.toString(ex.getRetryAfterSeconds()))
            .body(new ErrorResponse("ratelimit.exceeded", ex.getMessage()));
    }
}
