package com.llmgateway.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * Core Spring configuration for the gateway.
 */
@Configuration
@EnableConfigurationProperties(LlmProperties.class)
public class GatewayConfig {
}
