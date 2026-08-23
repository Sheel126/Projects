import time
from pathlib import Path

import httpx

from history_channel.config import settings


def atomic_write_bytes(dest: Path, data: bytes) -> None:
    """Write ``data`` to ``dest`` via a temp file + rename."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(dest)


def download_image(url: str, dest: Path) -> None:
    """Stream-download an image URL to ``dest`` with retries."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(settings.image_download_retries):
        try:
            with httpx.stream(
                "GET",
                url,
                follow_redirects=True,
                timeout=settings.image_download_timeout_sec,
            ) as response:
                response.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".tmp")
                with tmp.open("wb") as image_file:
                    for chunk in response.iter_bytes():
                        image_file.write(chunk)
                tmp.replace(dest)
            return
        except (httpx.HTTPError, OSError) as exc:
            last_error = exc
            if attempt + 1 < settings.image_download_retries:
                time.sleep(2**attempt)
    raise RuntimeError(
        f"Image download failed after {settings.image_download_retries} attempts: "
        f"{last_error}"
    ) from last_error
