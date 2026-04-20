# LLM Gateway

Production-oriented API gateway that proxies chat completions to OpenAI, Anthropic, and Google Gemini behind one canonical JSON API, with PostgreSQL (pgvector-ready), Redis, metrics, and OpenAPI docs.

## Quick start

```bash
cd llm-gateway
cp .env.example .env
# Set POSTGRES_PASSWORD, OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, GRAFANA_PASSWORD

cd docker
docker compose --env-file ../.env up --build
```

Verify liveness and proxy (replace the API key values with your real provider keys in `.env` for non-mocked traffic):

```bash
curl -sS http://localhost:8080/health -o /dev/null -w "%{http_code}\n"

curl -sS http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Say hi in one word."}],"userId":"demo"}'
```

- Swagger UI: http://localhost:8080/swagger-ui/index.html  
- Prometheus scrape path: http://localhost:8080/actuator/prometheus  
- Grafana (compose): http://localhost:3000  

## Architecture

See [docs/architecture.md](docs/architecture.md) for components, data stores, and request flow.

## Features (roadmap status)

| Area | Status |
|------|--------|
| Unified REST proxy (OpenAI, Anthropic, Gemini) | Phase 1 — implemented |
| Exact + semantic cache | Phase 2 — implemented (Redis exact + pgvector semantic via OpenAI embeddings) |
| API keys + sliding-window rate limits | Planned (Phase 3) |
| Resilience4j circuit breaker + failover table | Partial — basic model translation + health-based failover |
| Structured logs + Prometheus + Grafana | Logs JSON via Logstash encoder; Prometheus endpoint enabled |
| Cost tracking + budgets | Planned (Phase 6) |

## API reference

- [docs/api-reference.md](docs/api-reference.md)  
- Live OpenAPI: `/v3/api-docs` and Swagger UI above.

## Configuration

All environment variables are listed in [.env.example](.env.example). Spring reads the same names where applicable (for example `DATABASE_URL`, `SPRING_DATA_REDIS_URL`).

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | OpenAI bearer token |
| `ANTHROPIC_API_KEY` | Anthropic `x-api-key` |
| `GEMINI_API_KEY` | Gemini `key` query parameter |
| `POSTGRES_PASSWORD` / `DATABASE_*` | JDBC credentials |
| `REDIS_URL` | Redis URL fallback when `SPRING_DATA_REDIS_URL` is unset |
| `SPRING_DATA_REDIS_URL` | Preferred Spring property for Redis (Compose sets this) |
| `GRAFANA_PASSWORD` | Grafana admin password in compose |
| `SEMANTIC_CACHE_SIMILARITY_THRESHOLD` | Minimum cosine similarity (0–1) for semantic cache hits |
| `EXACT_CACHE_TTL_SECONDS` | TTL for Redis exact cache entries (seconds) |
| `SEMANTIC_CACHE_TTL_SECONDS` | TTL for semantic cache rows in Postgres (seconds; falls back to exact TTL when unset/0) |
| `EXACT_CACHE_ENABLED` | Set `false` to disable Redis exact caching |
| `SEMANTIC_CACHE_ENABLED` | Set `false` to disable semantic caching |
| `EMBEDDING_MODEL` | OpenAI embeddings model (must emit 1536 dimensions for current schema) |
| `DEFAULT_RATE_LIMIT_RPM` | Reserved (Phase 3) |

## Development

```bash
./gradlew test
```

- Unit tests always run on every machine.  
- `ChatCompletionIntegrationTest` and `SemanticCacheIntegrationTest` use Testcontainers (Postgres with pgvector, Redis) and WireMock for provider HTTP. They run automatically when Docker is available; otherwise they are skipped (`@Testcontainers(disabledWithoutDocker = true)`).  

### Adding a provider

1. Implement `LlmProvider` (map request, call HTTP, map response).  
2. Register the Spring `@Component` so it appears in `ProviderRouter`’s provider list.  
3. Extend `ModelTranslator` for cross-provider failover mappings.  
4. Add a WireMock stub branch in `ChatCompletionIntegrationTest` and a focused unit test if you introduce non-trivial logic.  

## Deployment

See [docs/deployment.md](docs/deployment.md).

## License

Open-source (add your SPDX license identifier when you publish the repo).
