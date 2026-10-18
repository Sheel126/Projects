"""Wires the LLM gateway from settings."""

import redis

from liquid_atm_quant.config import Settings
from liquid_atm_quant.infra.gpu_semaphore import GpuSemaphore
from liquid_atm_quant.llm.gateway import LlmGateway
from liquid_atm_quant.llm.ollama_client import OllamaClient


def build_gateway(settings: Settings, cache: redis.Redis) -> LlmGateway:
    return LlmGateway(
        client=OllamaClient(settings.ollama_base_url, timeout_s=settings.llm_timeout_seconds),
        cache=cache,
        semaphore=GpuSemaphore(cache, limit=settings.llm_max_concurrency),
        model=settings.llm_model,
        cache_ttl_s=settings.llm_cache_ttl_seconds,
    )
