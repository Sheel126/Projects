"""Phase 0 smoke test: local Qwen -> schema-constrained CatalystVerdict, run twice to prove the cache.

Usage (from liquid-atm/quant, with Redis up):  python scripts/llm_smoke.py
Exit code 0 = valid verdict produced; non-zero = the gate would have failed closed.
"""

import logging
import sys

from liquid_atm_quant.config import get_settings
from liquid_atm_quant.infra.redis_client import make_redis
from liquid_atm_quant.llm.factory import build_gateway
from liquid_atm_quant.llm.gateway import LlmRequest, LlmValidationError
from liquid_atm_quant.llm.ollama_client import OllamaClient, OllamaError
from liquid_atm_quant.llm.schemas import CatalystVerdict

SYSTEM = (
    "You are a skeptical equity risk manager. You receive recent filings/news for one stock that "
    "just broke out on high volume. Identify the catalyst and judge whether the move is backed by "
    "durable fundamentals or by hype. Use only the evidence given; if evidence is thin, say so with "
    "low confidence. Respond with JSON matching the provided schema."
)

# Fictional sample so the smoke test does not depend on network data.
SAMPLE_8K = """Ticker: ACME (fictional)
Form 8-K, Item 2.02 Results of Operations and Financial Condition
- Q2 revenue $2.41B vs consensus $2.18B (+10.5% beat), up 19% year over year.
- Diluted EPS $1.32 vs consensus $1.05.
- Full-year revenue guidance raised from $8.6-8.8B to $9.3-9.5B.
- Gross margin expanded 240bps on data-center product mix.
Price action: +11% on 3.4x average volume, closing at a 52-week high."""


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    settings = get_settings()

    ollama = OllamaClient(settings.ollama_base_url, timeout_s=5)
    try:
        models = ollama.list_models()
    except OllamaError as exc:
        print(f"FAIL: Ollama not reachable at {settings.ollama_base_url}: {exc}")
        return 2
    if settings.llm_model not in models:
        print(f"FAIL: model {settings.llm_model} not pulled. Run: ollama pull {settings.llm_model}")
        return 2

    gateway = build_gateway(settings, make_redis(settings))
    request = LlmRequest(task="catalyst_verdict", prompt_version="v0-smoke", system=SYSTEM, user=SAMPLE_8K)

    for run in (1, 2):
        try:
            result = gateway.run(request, CatalystVerdict)
        except LlmValidationError as exc:
            print(f"FAIL (gate fails closed): {exc}")
            return 1
        source = "CACHE" if result.cached else "OLLAMA"
        print(f"\n--- run {run} [{source}] model={result.model} latency={result.latency_ms} ms")
        if not result.cached:
            print(f"    tokens: prompt={result.prompt_tokens} completion={result.completion_tokens} "
                  f"speed={result.tokens_per_second:.1f} tok/s")
        print(result.value.model_dump_json(indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
