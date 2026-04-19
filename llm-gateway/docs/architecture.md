# Architecture

## Overview

Clients call the gateway’s **canonical** chat API (`POST /v1/chat/completions`). The gateway:

1. Validates the JSON body (`ChatRequest`).
2. Resolves a **primary** `LlmProvider` from the requested `model` id (prefix / support rules per adapter).
3. If the primary reports unhealthy (currently: missing API key), attempts **failover** to another healthy provider using `ModelTranslator` for cross-vendor model ids.
4. Returns a **canonical** `ChatResponse` (choice, usage, provider id, latency, `fromCache` always `false` until caching lands).

## Components

| Layer | Responsibility |
|-------|----------------|
| `api` | REST controllers, DTOs, exception mapping |
| `provider` | `LlmProvider` adapters (OpenAI, Anthropic, Gemini), `ProviderRouter`, `ModelTranslator` |
| `config` | `LlmProperties` binding from `llm.*` in `application.yml` |
| `observability` | Actuator health contributions (per-provider UP/DOWN) |

## Data stores

| Store | Role (current / planned) |
|-------|---------------------------|
| PostgreSQL + Flyway | `api_keys`, `usage_records`, `semantic_cache` (+ pgvector extension) — schema present; usage/auth/cache logic follows in later phases |
| Redis | Reserved for exact cache + rate limiting (Phase 2–3) |

## Observability

- **Logging**: JSON lines to stdout via Logstash Logback encoder (`logback-spring.xml`).
- **Metrics**: Micrometer Prometheus registry at `/actuator/prometheus`.
- **Health**: `/health` simple liveness; `/actuator/health` includes Redis and custom provider details.

## Docker stack

`docker/docker-compose.yml` runs the Spring app, Postgres (pgvector image), Redis, Prometheus, and Grafana on a single user-defined network so Prometheus can scrape `http://app:8080/actuator/prometheus`.
