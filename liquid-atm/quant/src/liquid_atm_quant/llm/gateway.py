"""LLM gateway: exact cache -> GPU slot -> Ollama (schema-constrained) -> validate, retry once, fail closed."""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Generic, TypeVar

import redis
from pydantic import BaseModel, ValidationError

from liquid_atm_quant.infra.gpu_semaphore import GpuSemaphore
from liquid_atm_quant.llm.ollama_client import OllamaClient

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LlmValidationError(RuntimeError):
    """The model did not produce a valid answer after the retry. Callers must treat this as a veto."""


@dataclass(frozen=True)
class LlmRequest:
    task: str            # e.g. "catalyst_verdict"
    prompt_version: str  # bump whenever the prompt wording changes
    system: str
    user: str


@dataclass(frozen=True)
class LlmResult(Generic[T]):
    value: T
    cached: bool
    cache_key: str
    model: str
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tokens_per_second: float = 0.0


def _canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class LlmGateway:
    def __init__(
        self,
        client: OllamaClient,
        cache: redis.Redis,
        semaphore: GpuSemaphore,
        model: str,
        cache_ttl_s: int,
    ) -> None:
        self._client = client
        self._cache = cache
        self._semaphore = semaphore
        self._model = model
        self._ttl = cache_ttl_s

    def cache_key(self, request: LlmRequest, output_model: type[BaseModel]) -> str:
        """Exact key: any change to model, prompt, schema or input text is a different key."""
        schema = output_model.model_json_schema()
        payload = {
            "model": self._model,
            "task": request.task,
            "prompt_version": request.prompt_version,
            "schema_sha": hashlib.sha256(_canonical_json(schema).encode()).hexdigest(),
            "system": request.system,
            "user": request.user,
        }
        digest = hashlib.sha256(_canonical_json(payload).encode()).hexdigest()
        return f"llm:{request.task}:{digest}"

    def run(self, request: LlmRequest, output_model: type[T]) -> LlmResult[T]:
        key = self.cache_key(request, output_model)
        started = time.perf_counter()

        hit = self._cache.get(key)
        if hit is not None:
            value = output_model.model_validate_json(hit)
            return LlmResult(value, True, key, self._model, int((time.perf_counter() - started) * 1000))

        schema = output_model.model_json_schema()
        messages = [
            {"role": "system", "content": request.system},
            {"role": "user", "content": request.user},
        ]
        last_error: Exception | None = None
        prompt_tokens = completion_tokens = 0
        tps = 0.0

        with self._semaphore.slot():
            for attempt in (1, 2):
                result = self._client.chat(self._model, messages, schema=schema, temperature=0.0)
                prompt_tokens += result.prompt_tokens
                completion_tokens += result.completion_tokens
                tps = result.tokens_per_second
                try:
                    value = output_model.model_validate_json(result.content)
                except ValidationError as exc:
                    last_error = exc
                    log.warning("llm.invalid_output task=%s attempt=%d errors=%d",
                                request.task, attempt, exc.error_count())
                    # Show the model its own answer and what was wrong with it, then retry once.
                    messages = messages + [
                        {"role": "assistant", "content": result.content},
                        {"role": "user", "content": f"Your answer failed validation:\n{exc}\n"
                                                    "Return corrected JSON only."},
                    ]
                    continue

                self._cache.set(key, value.model_dump_json(), ex=self._ttl)
                latency_ms = int((time.perf_counter() - started) * 1000)
                log.info("llm.call task=%s model=%s latency_ms=%d prompt_tokens=%d completion_tokens=%d tps=%.1f",
                         request.task, self._model, latency_ms, prompt_tokens, completion_tokens, tps)
                return LlmResult(value, False, key, self._model, latency_ms,
                                 prompt_tokens, completion_tokens, tps)

        # Fail closed: never cache a failure, never guess.
        raise LlmValidationError(f"{request.task}: invalid output after retry: {last_error}")
