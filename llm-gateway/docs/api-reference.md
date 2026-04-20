# API reference

Base URL: `http://localhost:8080` (or your deployed host).

## `GET /health`

Liveness probe. Returns `200` with an empty body when the process is up.

## `POST /v1/chat/completions`

**Request body** (`application/json`):

```json
{
  "model": "gpt-4o",
  "messages": [
    { "role": "user", "content": "Hello" }
  ],
  "temperature": 0.2,
  "maxTokens": 256,
  "userId": "optional-string"
}
```

- `model` must be supported by one of the built-in providers (for example `gpt-4o`, `claude-3-5-sonnet-20241022`, `gemini-1.5-pro`).
- `messages` follow OpenAI-style roles (`system`, `user`, `assistant`); adapters map them to vendor-specific payloads.

**Response** (`200`): canonical `ChatResponse` JSON — see `com.llmgateway.api.dto.ChatResponse` in source.

**Caching (Phase 2)**:

- **Exact**: identical canonical requests (including `userId` when present) hit Redis and set `fromCache` to `true` without calling the upstream chat endpoint again until TTL expiry.
- **Semantic**: when semantic caching is enabled and an OpenAI API key is configured, the gateway embeds the prompt text, searches prior rows in `semantic_cache` using pgvector cosine similarity, and may return a prior completion with `fromCache` true even when the raw prompt text differs slightly. Semantic misses still call the upstream provider; successful responses are stored with the configured TTL.

**Errors**:

- `400` — validation failures (`ErrorResponse` with `validation.failed`).
- `502` — upstream/provider failures (`ErrorResponse` with provider-specific codes such as `openai.http`).

## OpenAPI

Machine-readable schema: `GET /v3/api-docs`  
Interactive UI: `/swagger-ui/index.html`

## Actuator

- `GET /actuator/health` — component health (includes providers and Redis when configured).
- `GET /actuator/prometheus` — Prometheus text exposition format.
