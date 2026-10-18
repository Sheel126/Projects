package com.liquidatm.orchestrator;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

/**
 * Applies V1 to a real pgvector Postgres and checks that the schema enforces the rules
 * the rest of the system relies on.
 */
@SpringBootTest
@Testcontainers(disabledWithoutDocker = true)
class FlywayBaselineTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>(
        DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"));

    @Autowired
    JdbcTemplate jdbc;

    @Test
    void baselineCreatesAllTables() {
        List<String> tables = jdbc.queryForList(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'", String.class);
        assertThat(tables).contains(
            "instruments", "daily_bars", "universe_membership", "trading_calendar",
            "trade_intents", "orders", "fills", "tax_lots", "lot_disposals",
            "wash_sale_adjustments", "ticker_blacklist", "audit_log", "llm_calls");
        assertThat(jdbc.queryForObject(
            "SELECT count(*) FROM pg_extension WHERE extname = 'vector'", Integer.class)).isEqualTo(1);
    }

    @Test
    void barsRouteToYearPartition() {
        jdbc.update("""
            INSERT INTO daily_bars (symbol, trade_date, open, high, low, close, volume, source)
            VALUES ('SPY', DATE '2024-03-15', 510, 512, 508, 511, 1000000, 'alpaca_sip')""");
        assertThat(jdbc.queryForObject(
            "SELECT count(*) FROM daily_bars_2024 WHERE symbol = 'SPY'", Integer.class)).isEqualTo(1);
    }

    @Test
    void optionsAreRejectedByAssetClass() {
        assertThatThrownBy(() -> jdbc.update(
            "INSERT INTO instruments (symbol, asset_class) VALUES ('SPY240621C00500000', 'option')"))
            .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    void intentBracketMustBeOrdered() {
        jdbc.update("INSERT INTO instruments (symbol, asset_class) VALUES ('ACME', 'us_equity') ON CONFLICT DO NOTHING");
        assertThatThrownBy(() -> jdbc.update("""
            INSERT INTO trade_intents (intent_date, symbol, side, entry_limit, take_profit, stop_loss,
                                       risk_fraction, regime, reason)
            VALUES (DATE '2026-09-21', 'ACME', 'buy', 100, 95, 110, 0.01, 'bull', 'bad bracket')"""))
            .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    void clientOrderIdIsIdempotencyKey() {
        String insert = """
            INSERT INTO orders (client_order_id, symbol, side, order_type, order_class, qty, time_in_force, status)
            VALUES ('intent-42-entry', 'ACME', 'buy', 'limit', 'bracket', 10, 'day', 'new')""";
        jdbc.update(insert);
        assertThatThrownBy(() -> jdbc.update(insert)).isInstanceOf(DataIntegrityViolationException.class);
    }
}
