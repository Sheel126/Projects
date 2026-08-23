from history_channel.config import settings
from history_channel.providers.base import ImageGenerationProvider
from history_channel.providers.comfyui import ComfyUIImageProvider
from history_channel.providers.replicate import ReplicateImageProvider


def get_image_provider() -> ImageGenerationProvider:
    """Return the configured image generation provider.

    Supported values for ``IMAGE_PROVIDER``:
    - ``comfyui`` (default)
    - ``replicate``
    """
    provider = settings.image_provider.strip().lower()
    if provider == "comfyui":
        return ComfyUIImageProvider()
    if provider == "replicate":
        return ReplicateImageProvider()
    raise ValueError(
        f"Unknown IMAGE_PROVIDER={settings.image_provider!r}. "
        "Use 'comfyui' or 'replicate'."
    )
