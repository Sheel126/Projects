from fastapi import APIRouter, HTTPException

from history_channel.config import settings
from history_channel.schemas import ImageTestRequest, ImageTestResponse
from history_channel.services import image_service

router = APIRouter(prefix="/api/v1/images", tags=["images"])


@router.get("/provider")
def get_image_provider_info():
    """Return the active image provider and default dimensions."""
    return {
        "provider": settings.image_provider,
        "default_width": settings.comfyui_default_width,
        "default_height": settings.comfyui_default_height,
        "comfyui_base_url": settings.comfyui_base_url
        if settings.image_provider == "comfyui"
        else None,
    }


@router.post("/test", response_model=ImageTestResponse)
def generate_test_image(payload: ImageTestRequest):
    """Generate a single test image using the configured provider."""
    try:
        result = image_service.generate_test_image(
            payload.prompt,
            width=payload.width,
            height=payload.height,
            seed=payload.seed,
        )
        return ImageTestResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Test image generation failed: {exc}",
        ) from exc
