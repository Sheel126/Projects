import json

import httpx
import pytest
import respx

from liquid_atm_quant.infra.gpu_semaphore import GpuSemaphore
from liquid_atm_quant.llm.gateway import LlmGateway, LlmRequest, LlmValidationError
from liquid_atm_quant.llm.ollama_client import OllamaClient
from liquid_atm_quant.llm.schemas import CatalystVerdict

BASE = "http://ollama.test"
MODEL = "qwen2.5:14b-instruct"

VALID = {
    "catalyst_type": "earnings_beat",
    "quality": 0.8,
    "is_pump": False,
    "red_flags": [],
    "confidence": 0.7,
    "rationale": "Revenue and EPS beat with raised guidance.",
}


def ollama_reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={
        "message": {"role": "assistant", "content": content},
        "prompt_eval_count": 120, "eval_count": 60,
        "eval_duration": 2_000_000_000, "total_duration": 2_500_000_000, "done": True,
    })


@pytest.fixture
def gateway(redis_client):
    client = OllamaClient(BASE, http=httpx.Client(base_url=BASE))
    return LlmGateway(client, redis_client, GpuSemaphore(redis_client, limit=1), MODEL, cache_ttl_s=60)


def request(user: str = "8-K text", version: str = "v1") -> LlmRequest:
    return LlmRequest(task="catalyst_verdict", prompt_version=version, system="sys", user=user)


@respx.mock
def test_valid_answer_is_returned_and_schema_sent(gateway):
    route = respx.post(f"{BASE}/api/chat").mock(return_value=ollama_reply(json.dumps(VALID)))
    result = gateway.run(request(), CatalystVerdict)

    assert result.value.catalyst_type == "earnings_beat"
    assert not result.cached
    assert result.tokens_per_second == pytest.approx(30.0)
    body = json.loads(route.calls[0].request.content)
    assert body["model"] == MODEL
    assert body["stream"] is False
    assert body["options"]["temperature"] == 0.0
    assert body["format"]["properties"]["catalyst_type"]  # JSON schema passed to Ollama


@respx.mock
def test_second_identical_call_hits_cache(gateway):
    route = respx.post(f"{BASE}/api/chat").mock(return_value=ollama_reply(json.dumps(VALID)))
    first = gateway.run(request(), CatalystVerdict)
    second = gateway.run(request(), CatalystVerdict)

    assert route.call_count == 1
    assert second.cached
    assert second.value == first.value


@respx.mock
def test_any_input_or_prompt_change_misses_cache(gateway):
    route = respx.post(f"{BASE}/api/chat").mock(return_value=ollama_reply(json.dumps(VALID)))
    gateway.run(request(user="guidance raised"), CatalystVerdict)
    gateway.run(request(user="guidance cut"), CatalystVerdict)
    gateway.run(request(user="guidance cut", version="v2"), CatalystVerdict)
    assert route.call_count == 3


@respx.mock
def test_invalid_then_valid_retries_once(gateway):
    bad = dict(VALID, quality=1.7)  # out of range
    route = respx.post(f"{BASE}/api/chat").mock(side_effect=[
        ollama_reply(json.dumps(bad)), ollama_reply(json.dumps(VALID)),
    ])
    result = gateway.run(request(), CatalystVerdict)

    assert route.call_count == 2
    assert result.value.quality == 0.8
    retry_messages = json.loads(route.calls[1].request.content)["messages"]
    assert retry_messages[-1]["role"] == "user"
    assert "failed validation" in retry_messages[-1]["content"]


@respx.mock
def test_invalid_twice_fails_closed_and_is_not_cached(gateway, redis_client):
    respx.post(f"{BASE}/api/chat").mock(return_value=ollama_reply("not json at all"))
    with pytest.raises(LlmValidationError):
        gateway.run(request(), CatalystVerdict)
    assert redis_client.get(gateway.cache_key(request(), CatalystVerdict)) is None


@respx.mock
def test_health_checks_model_presence():
    respx.get(f"{BASE}/api/tags").mock(return_value=httpx.Response(200, json={"models": [{"name": MODEL}]}))
    client = OllamaClient(BASE, http=httpx.Client(base_url=BASE))
    assert client.is_healthy()
    assert client.is_healthy(MODEL)
    assert not client.is_healthy("qwen3:14b")


@respx.mock
def test_health_false_when_ollama_down():
    respx.get(f"{BASE}/api/tags").mock(side_effect=httpx.ConnectError("refused"))
    client = OllamaClient(BASE, http=httpx.Client(base_url=BASE))
    assert not client.is_healthy()
