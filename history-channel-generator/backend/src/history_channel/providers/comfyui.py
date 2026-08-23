"""Local ComfyUI image generation provider."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import httpx

from history_channel.config import settings
from history_channel.providers.base import ImageGenerationProvider
from history_channel.providers.comfyui_workflow import (
    DEFAULT_MAPPING,
    inject_workflow_parameters,
    load_workflow_template,
)
from history_channel.providers.types import ImageGenerationRequest, ImageGenerationResult

logger = logging.getLogger(__name__)

_TRANSIENT_STATUS_CODES = {502, 503, 504}


class ComfyUIUnavailableError(RuntimeError):
    """Raised when ComfyUI cannot be reached or returns a hard failure."""


class ComfyUIImageProvider(ImageGenerationProvider):
    """Generate images via a locally running ComfyUI HTTP API."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        workflow_path: Path | None = None,
        timeout_sec: float | None = None,
        poll_interval_sec: float | None = None,
        default_width: int | None = None,
        default_height: int | None = None,
        output_subdir: str | None = None,
    ) -> None:
        self._base_url = (base_url or settings.comfyui_base_url).rstrip("/")
        self._workflow_path = workflow_path or settings.comfyui_workflow_path_resolved()
        self._timeout_sec = timeout_sec or settings.comfyui_timeout_seconds
        self._poll_interval_sec = (
            poll_interval_sec or settings.comfyui_poll_interval_seconds
        )
        self._default_width = default_width or settings.comfyui_default_width
        self._default_height = default_height or settings.comfyui_default_height
        self._output_subdir = output_subdir or settings.comfyui_output_subdir

    @property
    def name(self) -> str:
        return "comfyui"

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        width = request.width or self._default_width
        height = request.height or self._default_height
        started = time.monotonic()

        workflow_template = load_workflow_template(self._workflow_path)
        workflow = inject_workflow_parameters(
            workflow_template,
            DEFAULT_MAPPING,
            prompt=request.prompt,
            width=width,
            height=height,
            seed=request.seed,
        )
        prompt_id = self._submit_prompt(workflow)
        outputs = self._wait_for_outputs(prompt_id)
        image_bytes = self._download_output_image(outputs)

        return ImageGenerationResult(
            provider=self.name,
            image_bytes=image_bytes,
            generation_time_sec=time.monotonic() - started,
            width=width,
            height=height,
            seed=self._extract_seed(workflow),
        )

    def _extract_seed(self, workflow: dict[str, Any]) -> int | None:
        try:
            return int(
                workflow[DEFAULT_MAPPING.seed_node]["inputs"][
                    DEFAULT_MAPPING.seed_field
                ]
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(30.0, read=self._timeout_sec),
        )

    def _request_with_retries(
        self,
        method: str,
        url: str,
        *,
        retries: int = 3,
        **kwargs: Any,
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                with self._client() as client:
                    response = client.request(method, url, **kwargs)
                if response.status_code in _TRANSIENT_STATUS_CODES:
                    raise httpx.HTTPStatusError(
                        f"Transient ComfyUI error {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                return response
            except (
                httpx.ConnectError,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.RemoteProtocolError,
                httpx.HTTPStatusError,
            ) as exc:
                last_error = exc
                if attempt + 1 < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break

        raise ComfyUIUnavailableError(
            f"ComfyUI is unavailable at {self._base_url}. "
            "Start ComfyUI locally and confirm COMFYUI_BASE_URL is correct. "
            f"Last error: {last_error}"
        ) from last_error

    def _submit_prompt(self, workflow: dict[str, Any]) -> str:
        response = self._request_with_retries(
            "POST",
            "/prompt",
            json={"prompt": workflow, "client_id": "history-channel-generator"},
        )
        if response.status_code >= 400:
            detail = response.text[:500]
            raise ComfyUIUnavailableError(
                f"ComfyUI rejected the workflow ({response.status_code}): {detail}"
            )
        payload = response.json()
        prompt_id = payload.get("prompt_id")
        if not prompt_id:
            raise ComfyUIUnavailableError(
                f"ComfyUI /prompt did not return prompt_id: {payload}"
            )
        logger.info("ComfyUI prompt submitted: %s", prompt_id)
        return str(prompt_id)

    def _wait_for_outputs(self, prompt_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self._timeout_sec
        while time.monotonic() < deadline:
            response = self._request_with_retries("GET", f"/history/{prompt_id}")
            if response.status_code == 404:
                time.sleep(self._poll_interval_sec)
                continue
            response.raise_for_status()
            history = response.json()
            if prompt_id not in history:
                time.sleep(self._poll_interval_sec)
                continue

            entry = history[prompt_id]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                messages = status.get("messages") or entry
                raise ComfyUIUnavailableError(
                    f"ComfyUI generation failed for prompt {prompt_id}: {messages}"
                )

            outputs = entry.get("outputs") or {}
            if outputs:
                return outputs

            time.sleep(self._poll_interval_sec)

        raise ComfyUIUnavailableError(
            f"ComfyUI timed out after {self._timeout_sec:.0f}s waiting for "
            f"prompt {prompt_id}."
        )

    def _download_output_image(self, outputs: dict[str, Any]) -> bytes:
        images = self._collect_output_images(outputs)
        if not images:
            raise ComfyUIUnavailableError(
                "ComfyUI completed but returned no SaveImage outputs."
            )

        image_meta = images[0]
        params = {
            "filename": image_meta["filename"],
            "type": image_meta.get("type", "output"),
        }
        if image_meta.get("subfolder"):
            params["subfolder"] = image_meta["subfolder"]

        response = self._request_with_retries("GET", "/view", params=params)
        response.raise_for_status()
        return response.content

    def _collect_output_images(self, outputs: dict[str, Any]) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        for node_output in outputs.values():
            if not isinstance(node_output, dict):
                continue
            images = node_output.get("images")
            if isinstance(images, list):
                collected.extend(img for img in images if isinstance(img, dict))
        return collected
