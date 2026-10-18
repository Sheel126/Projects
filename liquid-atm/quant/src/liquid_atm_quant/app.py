"""FastAPI entrypoint. Phase 0 exposes health only; intents arrive in later phases."""

import psycopg
import redis
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from liquid_atm_quant.config import get_settings
from liquid_atm_quant.infra.redis_client import make_redis
from liquid_atm_quant.llm.ollama_client import OllamaClient

app = FastAPI(title="liquid-atm quant", version="0.0.1")


@app.get("/health/live")
def live() -> dict[str, str]:
    """Process is up. Used by the container healthcheck."""
    return {"status": "UP"}


@app.get("/health")
def health() -> JSONResponse:
    """Dependency health.

    Redis and Postgres are required (DOWN -> 503). Ollama is reported but never fails the
    service: without the LLM the system must still run, it just opens no new positions.
    """
    settings = get_settings()
    checks: dict[str, str] = {}

    try:
        make_redis(settings).ping()
        checks["redis"] = "UP"
    except redis.RedisError as exc:
        checks["redis"] = f"DOWN: {exc}"

    try:
        with psycopg.connect(settings.database_url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        checks["postgres"] = "UP"
    except psycopg.Error as exc:
        checks["postgres"] = f"DOWN: {exc}"

    ollama = OllamaClient(settings.ollama_base_url, timeout_s=5)
    if not ollama.is_healthy():
        checks["ollama"] = "DOWN (no new entries)"
    elif not ollama.is_healthy(settings.llm_model):
        checks["ollama"] = f"DEGRADED: model {settings.llm_model} not pulled"
    else:
        checks["ollama"] = "UP"

    required_ok = checks["redis"] == "UP" and checks["postgres"] == "UP"
    body = {"status": "UP" if required_ok else "DOWN", "checks": checks, "model": settings.llm_model}
    return JSONResponse(body, status_code=200 if required_ok else 503)
