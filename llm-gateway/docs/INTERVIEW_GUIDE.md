# LLM Gateway — Interview Guide (Phases 1–3)

This document is a “tell the story” guide you can use in interviews. It summarizes what the project does, why it exists, and what you implemented in each phase so far (with special focus on Phase 3 and the DSA-style sliding-window algorithm).

## 30-second pitch

**LLM Gateway** is a production-oriented API gateway that exposes **one canonical chat API** and proxies requests to **OpenAI, Anthropic, and Google Gemini**. It adds platform features you’d need in a real product:

- **Caching**: Redis exact-cache + Postgres/pgvector semantic cache
- **Reliability routing**: provider adapters + model translation + health-based failover
- **Observability**: JSON structured logs + Prometheus metrics (+ Grafana via docker-compose)
- **Phase 3 security**: API keys (hashed at rest) + Redis **sliding-window** rate limiting

## What I’d demo live

- Start the stack with Docker Compose (`docker compose --env-file ../.env up --build`)
- Hit `/health`
- Call `POST /v1/chat/completions` with a model like `gpt-4o`
- Show caching:
  - Make the same request twice and point out `fromCache=true` on the second call
- Enable Phase 3 auth + rate limiting:
  - Create a gateway API key via `POST /v1/admin/api-keys` (protected by `X-Admin-Token`)
  - Call `GET /v1/whoami` with `X-API-Key`
  - Spam the endpoint to trigger a `429` and explain the sliding-window implementation

## Architecture (high level)

Request flow for `POST /v1/chat/completions`:

1. **(Phase 3, optional)** Authenticate `X-API-Key` and apply a **sliding-window** rate limit in Redis.
2. Validate request DTO (`ChatRequest`) using Spring validation.
3. Check caches:
   - **Exact cache** in Redis using a canonical request hash
   - **Semantic cache** in Postgres using pgvector cosine similarity (embedding via OpenAI embeddings API)
4. Route to a provider adapter (`OpenAiProvider`, `AnthropicProvider`, `GeminiProvider`) based on `model`.
5. Fail over to another provider when needed (health + `ModelTranslator` mappings).
6. Return a canonical `ChatResponse` with `provider`, `latencyMs`, and `fromCache`.

## Phase-by-phase: what’s implemented

### Phase 1 — Unified proxy + provider adapters

**Goal**: one stable API for the client while still using multiple LLM vendors.

**Implemented**:

- Canonical endpoint: `POST /v1/chat/completions`
- Provider adapters:
  - OpenAI chat completions
  - Anthropic messages
  - Gemini generateContent
- Canonical response: `ChatResponse` with normalized message/usage/provider fields
- Integration tests using WireMock to simulate upstream providers

**Interview angle**:

- Clear abstraction boundary (`LlmProvider`) + routing layer (`ProviderRouter`)
- “Vendor lock-in reduction” story: client code doesn’t change when provider changes

### Phase 2 — Caching (exact + semantic)

**Goal**: reduce latency and cost; avoid repeated upstream calls.

**Implemented**:

- **Exact caching** in Redis:
  - Key: SHA-256 of canonical request JSON
  - Value: serialized `ChatResponse`
  - TTL: `EXACT_CACHE_TTL_SECONDS`
- **Semantic caching** in Postgres with pgvector:
  - Embed prompt text via OpenAI embeddings (`EMBEDDING_MODEL`)
  - Lookup by cosine similarity threshold (`SEMANTIC_CACHE_SIMILARITY_THRESHOLD`)
  - Store responses with TTL
- Flyway migrations for schema (`semantic_cache`, `usage_records`, `api_keys`)

**Interview angle**:

- Layered caching and explicit feature flags (`EXACT_CACHE_ENABLED`, `SEMANTIC_CACHE_ENABLED`)
- Clear tradeoffs: semantic caching requires embeddings cost + false positives/negatives

### Phase 3 — API keys + sliding-window rate limiting (this work)

**Goal**: make the gateway multi-tenant and production-like (authn + abuse prevention).

**Implemented**:

- API keys stored in Postgres `api_keys` **as HMAC-SHA256 hashes** (no plaintext at rest)
- Gateway request filter:
  - Requires `X-API-Key` when enabled
  - Sets request attributes: `apiKeyId`, `userId`
- Admin endpoints (protected by `X-Admin-Token` == `GATEWAY_ADMIN_TOKEN`):
  - `POST /v1/admin/api-keys` returns a key once
  - `DELETE /v1/admin/api-keys/{id}` revokes
- Rate limiting via Redis **sliding window**:
  - Each request adds a timestamp (ms) to a Redis **sorted set**
  - A Lua script atomically:
    - evicts timestamps older than the window
    - counts remaining requests
    - allows or blocks the next request
  - On block, the API returns `429` with `Retry-After`

#### Sliding window: DSA explanation (what I’d say in an interview)

This is the core algorithmic piece recruiters like because it’s a real system problem with data-structure choices:

- **Data structure**: Redis **ZSET** (sorted set)
  - Score = request timestamp
  - Member = unique id (`<timestamp>-<uuid>`)
- **Operations per request** (all inside one atomic Lua script):
  - `ZREMRANGEBYSCORE(key, 0, now-window)` removes old events
  - `ZCARD(key)` counts events still inside the window
  - If count >= limit → block
  - Else `ZADD(key, now, member)` and `EXPIRE(key, window+buffer)` → allow
- **Complexity intuition**:
  - Eviction is proportional to number of expired entries removed
  - Counting is efficient in Redis
  - Atomic script avoids race conditions under concurrency

## “Google-ready” talking points

- **Clean boundaries**: adapters (providers), orchestration (service), infrastructure (Redis/Postgres), and HTTP concerns (filter/controllers)
- **Real infra**: Postgres + Redis + metrics stack via docker-compose; integration tests use Testcontainers
- **Security basics**: hashed secrets at rest, admin token for privileged endpoints, revocation support
- **Algorithmic highlight**: sliding window implemented via ZSET + Lua (atomicity + correctness)

## How to answer “What would you improve next?”

- Add usage-based cost tracking and monthly budgets (schema already has `usage_records` + `monthly_budget_usd`)
- Add per-route rate limits and burst handling (token bucket or leaky bucket vs sliding window)
- Add RBAC or scoped API keys (read-only vs write)
- Add stronger auth (JWT) for end-users, keep API keys for machine-to-machine
- Add circuit breaker (Resilience4j) and real provider health signals (timeouts, 5xx rates)

