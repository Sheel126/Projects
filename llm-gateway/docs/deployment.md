# Deployment

## Docker Compose (recommended for Phase 1)

1. Copy `.env.example` to `.env` at the repo root (`llm-gateway/.env`).
2. Set strong secrets: `POSTGRES_PASSWORD`, provider API keys, `GRAFANA_PASSWORD`.
3. From `llm-gateway/docker`:

```bash
docker compose --env-file ../.env up --build
```

The `app` service waits for Postgres and Redis health checks before starting. The image is built multi-stage: Gradle `bootJar` inside a JDK image, then a slim JRE runtime.

## Ports

| Port | Service |
|------|---------|
| **8081** (host) → 8080 (container) | LLM Gateway — mapped to **8081** on the host so it can run alongside **polyglot-system**, which uses host **8080** for its Java API. |
| 5432 | Postgres (not published by default; add `ports` if you need host access) |
| 6379 | Redis (internal only unless published) |
| 9090 | Prometheus |
| 3000 | Grafana |

## Prometheus

`docker/prometheus/prometheus.yml` scrapes `app:8080` on the Compose network. On Linux hosts without Docker Desktop, replace targets with the published gateway port if you run Prometheus outside Compose.

## Production notes

- Terminate TLS at your edge (reverse proxy or cloud LB); the app serves plain HTTP on port 8080.
- Rotate provider keys via environment / secret manager; never commit `.env`.
- Tune JVM memory and `SPRING_DATASOURCE_HIKARI_*` pool sizes under load (future hardening).
