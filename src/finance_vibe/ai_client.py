from __future__ import annotations

import json
import os
import time
from typing import Iterable, List, Sequence

import requests

try:
    from finance_vibe import config
    from finance_vibe.ai_models import AIAnalysisResult, validate_ai_payload
except ImportError:
    from . import config
    from .ai_models import AIAnalysisResult, validate_ai_payload


AI_DEFAULT_MODEL = config.AI_MODEL
AI_MAX_RETRIES = config.AI_MAX_RETRIES
AI_REQUEST_TIMEOUT = config.AI_REQUEST_TIMEOUT


class AIClientError(Exception):
    pass


def _build_prompt_for_batch(rows: Sequence[dict]) -> str:
    """
    Build a compact, model-friendly prompt for a batch of trade plan
    rows (already enriched with any news/events). The AI is instructed
    to return ONLY JSON.
    """
    instructions = {
        "role": "system",
        "content": (
            "You are an experienced swing trader. You receive weekly swing "
            "setups with fields like symbol, setup_type, stock_entry, "
            "stock_stop, targets, ema20, ema50, rsi, atr and optional "
            "news headlines with sentiment. For each input row you must "
            "return a JSON object with keys: symbol, setup_type, "
            "recommendation (TAKE, WATCH, or SKIP), time_horizon, "
            "confidence (0.0-1.0), risk_flags (array of strings), "
            "rationale_bullets (array of short sentences), invalidations "
            "(array of short sentences), action_plan (3-5 clear steps for "
            "what the user should do next), beginner_notes (2-4 plain "
            "language notes for first-time investors), position_size_hint "
            "(one short sentence), buy_timing (one sentence for when to "
            "enter), sell_timing (one sentence for when to take profits / "
            "exit), news_headlines (array of {title, url, "
            "sentiment}). Focus on risk-aware swing trading logic and do "
            "not give portfolio-level advice."
        ),
    }
    user = {
        "role": "user",
        "content": (
            "Analyze the following swing trade plan rows and respond with a "
            "strict JSON array where each element corresponds 1:1 to an "
            "input row.\n\n"
            "INPUT_ROWS_JSON:\n"
            + json.dumps(rows, ensure_ascii=False)
            + "\n\n"
            "OUTPUT_FORMAT:\n"
            "[\n"
            "  {\n"
            '    \"symbol\": \"SPY\",\n'
            '    \"setup_type\": \"SETUP_LONG\",\n'
            '    \"recommendation\": \"TAKE\",\n'
            '    \"time_horizon\": \"1-3 weeks\",\n'
            '    \"confidence\": 0.8,\n'
            '    \"risk_flags\": [\"earnings_soon\"],\n'
            '    \"rationale_bullets\": [\"Uptrend with pullback to EMA20\"],\n'
            '    \"invalidations\": [\"Close below EMA50 on a weekly basis\"],\n'
            '    \"action_plan\": [\n'
            '      \"Set price alert at entry level\",\n'
            '      \"Only enter after weekly close confirms setup\",\n'
            '      \"Pre-place stop at invalidation level\"\n'
            "    ],\n"
            '    \"beginner_notes\": [\n'
            '      \"A WATCH means wait for confirmation before buying\",\n'
            '      \"Do not risk money you cannot afford to lose\"\n'
            "    ],\n"
            '    \"position_size_hint\": \"Start with a small starter position and add only if setup confirms\",\n'
            '    \"buy_timing\": \"Enter after price reclaims and holds above the planned entry level\",\n'
            '    \"sell_timing\": \"Take partial profit at target 1, more at target 2, and fully exit if stop is hit\",\n'
            '    \"news_headlines\": [\n'
            '      {\"title\": \"Example\", \"url\": \"https://example.com\", '
            '\"sentiment\": \"mixed\"}\n'
            "    ]\n"
            "  }\n"
            "]\n\n"
            "Return ONLY the JSON array, with no extra commentary."
        ),
    }
    return json.dumps([instructions, user], ensure_ascii=False)


def _call_openai_chat_api(prompt_payload: str) -> str:
    """
    Minimal HTTP wrapper around an OpenAI-compatible chat API.
    This is intentionally simple so it can be swapped out later.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    if not api_key:
        raise AIClientError("OPENAI_API_KEY is not set in the environment.")

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # prompt_payload is a JSON-encoded list of messages
    messages = json.loads(prompt_payload)

    body = {
        "model": AI_DEFAULT_MODEL,
        "messages": messages,
        "temperature": 0.2,
    }

    resp = requests.post(
        url,
        headers=headers,
        json=body,
        timeout=AI_REQUEST_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise AIClientError(
            f"LLM API error {resp.status_code}: {resp.text[:500]}"
        )

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return content


def analyze_tickers_batch(
    rows: Sequence[dict],
    sleep_between_retries: float = 2.0,
) -> List[AIAnalysisResult]:
    """
    Analyze a batch of enriched trade-plan rows with the LLM and return
    validated AIAnalysisResult instances. On repeated failure, returns
    fallback results with status flags so callers can continue.
    """
    if not rows:
        return []

    prompt_payload = _build_prompt_for_batch(rows)

    last_error: str | None = None
    for attempt in range(AI_MAX_RETRIES + 1):
        try:
            raw = _call_openai_chat_api(prompt_payload)
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                # Some providers may still wrap the array; attempt best-effort fix
                # by locating the first '[' and last ']'.
                start = raw.find("[")
                end = raw.rfind("]")
                if start != -1 and end != -1 and end > start:
                    parsed = json.loads(raw[start : end + 1])
                else:
                    raise

            if not isinstance(parsed, list):
                raise AIClientError("Expected JSON array from model.")

            results: List[AIAnalysisResult] = []
            for idx, obj in enumerate(parsed):
                if not isinstance(obj, dict):
                    raise AIClientError(
                        f"Array element {idx} is not an object: {type(obj)}"
                    )
                res = validate_ai_payload(obj)
                results.append(res)

            # If model returned fewer results than rows, pad with defaults.
            if len(results) < len(rows):
                for extra in rows[len(results) :]:
                    results.append(
                        AIAnalysisResult(
                            symbol=str(extra.get("Symbol", "")).strip(),
                            setup_type=str(
                                extra.get("Setup Type", "SETUP_LONG")
                            ),  # type: ignore[arg-type]
                            recommendation="WATCH",  # type: ignore[arg-type]
                            time_horizon="1-3 weeks",
                            confidence=0.0,
                            status="validation_failed",
                            raw_model_output=raw,
                        )
                    )

            return results
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            if attempt < AI_MAX_RETRIES:
                time.sleep(sleep_between_retries * (attempt + 1))
                continue

            # Fall back: mark all rows as unavailable for this batch.
            fallback: List[AIAnalysisResult] = []
            for r in rows:
                fallback.append(
                    AIAnalysisResult(
                        symbol=str(r.get("Symbol", "")).strip(),
                        setup_type=str(
                            r.get("Setup Type", "SETUP_LONG")
                        ),  # type: ignore[arg-type]
                        recommendation="WATCH",  # type: ignore[arg-type]
                        time_horizon="1-3 weeks",
                        confidence=0.0,
                        status="ai_unavailable",
                        raw_model_output=last_error,
                    )
                )
            return fallback


def analyze_tickers_stream(
    rows: Iterable[dict],
    batch_size: int,
) -> List[AIAnalysisResult]:
    """
    Convenience helper that slices an iterable of rows into batches and
    calls analyze_tickers_batch for each.
    """
    batch: list[dict] = []
    all_results: list[AIAnalysisResult] = []

    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            all_results.extend(analyze_tickers_batch(batch))
            batch.clear()

    if batch:
        all_results.extend(analyze_tickers_batch(batch))

    return all_results

