package com.liquidatm.orchestrator;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Execution orchestrator: the only component allowed to move money.
 *
 * <p>Phase 0 owns the database schema (Flyway) and exposes health. The intent consumer,
 * Alpaca OMS, tax ledger and kill switches arrive in Phases 6-7.
 */
@SpringBootApplication
public class OrchestratorApplication {

    public static void main(String[] args) {
        SpringApplication.run(OrchestratorApplication.class, args);
    }
}
