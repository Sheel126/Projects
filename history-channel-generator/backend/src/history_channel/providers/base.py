from abc import ABC, abstractmethod
from pathlib import Path

from history_channel.providers.types import ImageGenerationRequest, ImageGenerationResult


class ImageGenerationProvider(ABC):
    """Provider abstraction for scene and test image generation."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short provider identifier (e.g. ``comfyui``, ``replicate``)."""

    @abstractmethod
    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate a single image from ``request``."""

    def generate_to_file(
        self, request: ImageGenerationRequest, dest: Path
    ) -> ImageGenerationResult:
        """Generate an image and save it atomically to ``dest``."""
        from history_channel.providers.io import atomic_write_bytes, download_image

        result = self.generate(request)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if result.image_bytes is not None:
            atomic_write_bytes(dest, result.image_bytes)
        elif result.image_url:
            download_image(result.image_url, dest)
        else:
            raise RuntimeError(
                f"{self.name} returned no image bytes or URL for {dest.name}"
            )
        return result
