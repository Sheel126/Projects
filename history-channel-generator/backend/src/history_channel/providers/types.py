from dataclasses import dataclass


@dataclass(frozen=True)
class ImageGenerationRequest:
    prompt: str
    width: int | None = None
    height: int | None = None
    seed: int | None = None
    negative_prompt: str | None = None
    aspect_ratio: str = "16:9"


@dataclass(frozen=True)
class ImageGenerationResult:
    provider: str
    image_bytes: bytes | None = None
    image_url: str | None = None
    generation_time_sec: float | None = None
    width: int | None = None
    height: int | None = None
    seed: int | None = None
