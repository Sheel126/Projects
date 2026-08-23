"""Optional Replicate Flux provider (fallback when IMAGE_PROVIDER=replicate)."""

from __future__ import annotations

import re
import time

import replicate
from replicate.exceptions import ReplicateError

from history_channel.config import settings
from history_channel.providers.base import ImageGenerationProvider
from history_channel.providers.types import ImageGenerationRequest, ImageGenerationResult

REPLICATE_MIN_INTERVAL_SEC = 12.0
REPLICATE_MAX_RETRIES = 5

_last_replicate_call_at = 0.0


def _parse_retry_after_seconds(error: Exception) -> float:
    text = str(error)
    match = re.search(r"resets in ~?(\d+)\s*s", text, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1.0
    return REPLICATE_MIN_INTERVAL_SEC


def _wait_for_rate_limit() -> None:
    global _last_replicate_call_at
    elapsed = time.monotonic() - _last_replicate_call_at
    if elapsed < REPLICATE_MIN_INTERVAL_SEC:
        time.sleep(REPLICATE_MIN_INTERVAL_SEC - elapsed)


class ReplicateImageProvider(ImageGenerationProvider):
    @property
    def name(self) -> str:
        return "replicate"

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        global _last_replicate_call_at

        if not settings.replicate_api_token:
            raise ValueError(
                "Replicate API token is required when IMAGE_PROVIDER=replicate"
            )

        client = replicate.Client(
            api_token=settings.replicate_api_token,
            timeout=settings.image_generation_timeout_sec,
        )
        last_error: Exception | None = None
        started = time.monotonic()

        for _attempt in range(REPLICATE_MAX_RETRIES):
            _wait_for_rate_limit()
            try:
                output = client.run(
                    settings.flux_model,
                    input={
                        "prompt": request.prompt,
                        "aspect_ratio": request.aspect_ratio,
                        "output_format": "png",
                        "output_quality": 90,
                        "negative_prompt": (
                            request.negative_prompt or settings.flux_negative_prompt
                        ),
                    },
                    wait=min(60, int(settings.image_generation_timeout_sec)),
                )
                _last_replicate_call_at = time.monotonic()
                if isinstance(output, list):
                    url = str(output[0])
                else:
                    url = str(output)
                return ImageGenerationResult(
                    provider=self.name,
                    image_url=url,
                    generation_time_sec=time.monotonic() - started,
                )
            except ReplicateError as exc:
                last_error = exc
                status = getattr(exc, "status", None)
                if status == 429 or "429" in str(exc) or "throttled" in str(exc).lower():
                    wait_s = _parse_retry_after_seconds(exc)
                    time.sleep(wait_s)
                    _last_replicate_call_at = time.monotonic()
                    continue
                raise
            except Exception as exc:
                if "429" in str(exc) or "throttled" in str(exc).lower():
                    last_error = exc
                    wait_s = _parse_retry_after_seconds(exc)
                    time.sleep(wait_s)
                    _last_replicate_call_at = time.monotonic()
                    continue
                raise

        raise RuntimeError(
            "Replicate rate limit exceeded after retries. "
            "Free-tier accounts are capped at ~6 predictions/min until you add a "
            "payment method at https://replicate.com/account/billing. "
            f"Last error: {last_error}"
        )
