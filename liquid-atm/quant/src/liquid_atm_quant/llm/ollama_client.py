"""Thin client for the local Ollama REST API."""

from dataclasses import dataclass
from typing import Any

import httpx


class OllamaError(RuntimeError):
    """Ollama was unreachable or returned an unusable response."""


@dataclass(frozen=True)
class ChatResult:
    content: str
    prompt_tokens: int
    completion_tokens: int
    eval_duration_ns: int
    total_duration_ns: int

    @property
    def tokens_per_second(self) -> float:
        if self.eval_duration_ns <= 0:
            return 0.0
        return self.completion_tokens / (self.eval_duration_ns / 1e9)


class OllamaClient:
    def __init__(self, base_url: str, timeout_s: float = 300.0, http: httpx.Client | None = None) -> None:
        self._http = http or httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_s)

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        num_predict: int | None = None,
    ) -> ChatResult:
        options: dict[str, Any] = {"temperature": temperature}
        if num_predict is not None:
            options["num_predict"] = num_predict
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        if schema is not None:
            # A JSON Schema here constrains sampling so the output must parse into it.
            body["format"] = schema
        try:
            resp = self._http.post("/api/chat", json=body)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError(f"ollama chat failed: {exc}") from exc

        message = data.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise OllamaError("ollama response missing message.content")
        return ChatResult(
            content=content,
            prompt_tokens=int(data.get("prompt_eval_count", 0)),
            completion_tokens=int(data.get("eval_count", 0)),
            eval_duration_ns=int(data.get("eval_duration", 0)),
            total_duration_ns=int(data.get("total_duration", 0)),
        )

    def list_models(self) -> list[str]:
        try:
            resp = self._http.get("/api/tags", timeout=5)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise OllamaError(f"ollama tags failed: {exc}") from exc

    def is_healthy(self, model: str | None = None) -> bool:
        try:
            models = self.list_models()
        except OllamaError:
            return False
        return model is None or model in models
