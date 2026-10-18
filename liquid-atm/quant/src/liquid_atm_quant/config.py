"""Typed settings loaded from environment variables (and `.env` when present)."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# liquid-atm/.env, so scripts work no matter which directory they are launched from.
_PROJECT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_PROJECT_ENV, extra="ignore")

    # Broker
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True

    # Local LLM
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:14b-instruct"
    llm_max_concurrency: int = Field(default=1, ge=1)
    llm_timeout_seconds: float = 300.0
    llm_cache_ttl_seconds: int = 7 * 24 * 3600

    # Infra
    database_url: str = "postgresql://liquidatm:change-me@localhost:5433/liquidatm"
    redis_url: str = "redis://localhost:6380/0"

    # SEC EDGAR (Phase 1)
    sec_user_agent: str = ""

    @property
    def has_alpaca_keys(self) -> bool:
        return bool(self.alpaca_api_key and self.alpaca_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
