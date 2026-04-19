package com.llmgateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Entry point for the LLM Gateway Spring Boot application.
 */
@SpringBootApplication
public class GatewayApplication {

    /**
     * Bootstraps the Spring context and starts the embedded web server.
     *
     * @param args standard Spring Boot command-line arguments
     */
    public static void main(String[] args) {
        SpringApplication.run(GatewayApplication.class, args);
    }
}
