# Architecture

## Overview

Clients call the gateway’s **canonical** chat API (`POST /v1/chat/completions`). The gateway:

1. (Phase 3, optional) Authenticates `X-API-Key` against `api_keys` (HMAC-hashed at rest) and applies a Redis **sliding-window** rate limit.
2. Validates the JSON body (`ChatRequest`).
3. Checks **Phase 2 caches** in order: Redis **exact** key (canonical request hash), then Postgres **semantic** match (OpenAI embedding cosine similarity against `semantic_cache` when enabled and an OpenAI API key is present).
4. Resolves a **primary** `LlmProvider` from the requested `model` id (prefix / support rules per adapter).
5. If the primary reports unhealthy (currently: missing API key), attempts **failover** to another healthy provider using `ModelTranslator` for cross-vendor model ids.
6. Returns a **canonical** `ChatResponse` (choice, usage, provider id, latency, `fromCache` when served from cache).

## Components

| Layer | Responsibility |
|-------|----------------|
| `api` | REST controllers, DTOs, exception mapping |
| `provider` | `LlmProvider` adapters (OpenAI, Anthropic, Gemini), `ProviderRouter`, `ModelTranslator` |
| `config` | `LlmProperties` and `CacheProperties` binding from `llm.*` in `application.yml` |
| `cache` / `service` | Redis exact cache, pgvector semantic cache, OpenAI embeddings client, `ChatCompletionService` orchestration |
| `observability` | Actuator health contributions (per-provider UP/DOWN) |

## Data stores

| Store | Role (current / planned) |
|-------|---------------------------|
| PostgreSQL + Flyway | `api_keys`, `usage_records`, `semantic_cache` (+ pgvector extension) — semantic cache reads/writes active in Phase 2 |
| Redis | Exact response cache (Phase 2) + sliding-window rate limiting buckets (Phase 3) |

## Observability

- **Logging**: JSON lines to stdout via Logstash Logback encoder (`logback-spring.xml`).
- **Metrics**: Micrometer Prometheus registry at `/actuator/prometheus`.
- **Health**: `/health` simple liveness; `/actuator/health` includes Redis and custom provider details.

## Docker stack

`docker/docker-compose.yml` runs the Spring app, Postgres (pgvector image), Redis, Prometheus, and Grafana on a single user-defined network so Prometheus can scrape `http://app:8080/actuator/prometheus`.
