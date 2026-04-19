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

**Errors**:

- `400` — validation failures (`ErrorResponse` with `validation.failed`).
- `502` — upstream/provider failures (`ErrorResponse` with provider-specific codes such as `openai.http`).

## OpenAPI

Machine-readable schema: `GET /v3/api-docs`  
Interactive UI: `/swagger-ui/index.html`

## Actuator

- `GET /actuator/health` — component health (includes providers and Redis when configured).
- `GET /actuator/prometheus` — Prometheus text exposition format.
