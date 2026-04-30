package com.llmgateway.security;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public class ApiKeyRepository {

    private final JdbcTemplate jdbc;

    public ApiKeyRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<ApiKeyPrincipal> findActiveByHash(String keyHash) {
        List<ApiKeyPrincipal> rows = jdbc.query(
            """
                SELECT id, user_id, rate_limit
                FROM api_keys
                WHERE key_hash = ? AND revoked_at IS NULL
                LIMIT 1
            """,
            principalRowMapper(),
            keyHash
        );
        return rows.stream().findFirst();
    }

    public UUID insert(String keyHash, String name, String userId, Integer rateLimitRpm) {
        UUID id = jdbc.queryForObject(
            """
                INSERT INTO api_keys (key_hash, name, user_id, rate_limit)
                VALUES (?, ?, ?, COALESCE(?, 100))
                RETURNING id
            """,
            UUID.class,
            keyHash,
            name,
            userId,
            rateLimitRpm
        );
        if (id == null) {
            throw new IllegalStateException("api_keys insert returned null id");
        }
        return id;
    }

    public int revoke(UUID id) {
        return jdbc.update(
            "UPDATE api_keys SET revoked_at = now() WHERE id = ? AND revoked_at IS NULL",
            id
        );
    }

    private static RowMapper<ApiKeyPrincipal> principalRowMapper() {
        return (rs, rowNum) -> new ApiKeyPrincipal(
            UUID.fromString(rs.getString("id")),
            rs.getString("user_id"),
            rs.getInt("rate_limit")
        );
    }
}

