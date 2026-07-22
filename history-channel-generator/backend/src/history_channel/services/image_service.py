import re
import time
import urllib.request
from pathlib import Path

import replicate
from replicate.exceptions import ReplicateError
from sqlalchemy.orm import Session

from history_channel.agents.image_prompt_agent import generate_scene_prompts
from history_channel.config import settings
from history_channel.models import GeneratedImage, ProjectStatus, ProjectTopic, Scene

# Free-tier accounts are limited to ~6 predictions/min with burst of 1.
REPLICATE_MIN_INTERVAL_SEC = 12.0
REPLICATE_MAX_RETRIES = 5

_last_replicate_call_at = 0.0


def _download_image(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)


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


def _generate_flux_image(prompt: str) -> str:
    global _last_replicate_call_at

    if not settings.replicate_api_token:
        raise ValueError("Replicate API token is required for image generation")

    client = replicate.Client(api_token=settings.replicate_api_token)
    last_error: Exception | None = None

    for _attempt in range(REPLICATE_MAX_RETRIES):
        _wait_for_rate_limit()
        try:
            output = client.run(
                settings.flux_model,
                input={
                    "prompt": prompt,
                    "aspect_ratio": "16:9",
                    "output_format": "png",
                    "output_quality": 90,
                    # Schnell ignores negative_prompt on some versions; harmless if present
                    "negative_prompt": settings.flux_negative_prompt,
                },
            )
            _last_replicate_call_at = time.monotonic()
            if isinstance(output, list):
                return str(output[0])
            return str(output)
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
        "Free-tier accounts are capped at ~6 predictions/min until you add a payment "
        f"method at https://replicate.com/account/billing. Last error: {last_error}"
    )


def _generate_scene_image(
    db: Session,
    project: ProjectTopic,
    scene: Scene,
    order: int,
    out_dir: Path,
) -> GeneratedImage:
    """Generate exactly one image per scene and auto-select it."""
    image_url = _generate_flux_image(scene.image_prompt or "")
    file_path = out_dir / f"scene_{order}.png"
    _download_image(image_url, file_path)

    img = GeneratedImage(
        project_id=project.id,
        scene_id=scene.id,
        variation_index=0,
        file_path=str(file_path),
        is_thumbnail=False,
    )
    db.add(img)
    db.flush()
    scene.selected_image_id = img.id
    return img


def generate_images(db: Session, project: ProjectTopic) -> ProjectTopic:
    from history_channel.readiness import can_generate_images, hash_script

    if not can_generate_images(project):
        raise ValueError(
            "Audio must exist on disk before images "
            "(status is ignored — regenerate audio if the file is missing)"
        )
    if not project.script_text:
        raise ValueError("Script is required for image generation")

    min_scenes, _max_scenes = settings.scene_count_range(project.is_test_mode)
    scene_count = min_scenes  # fixed count (test=3, prod=12)

    out_dir = settings.project_output_dir(project.id) / "images"
    out_dir.mkdir(parents=True, exist_ok=True)

    scene_prompts = generate_scene_prompts(project.script_text, scene_count)

    db.query(GeneratedImage).filter(GeneratedImage.project_id == project.id).delete()

    existing_scenes = (
        db.query(Scene)
        .filter(Scene.project_id == project.id)
        .order_by(Scene.scene_order.asc())
        .all()
    )

    first_image: GeneratedImage | None = None

    if existing_scenes:
        for order, scene_data in enumerate(scene_prompts):
            if order < len(existing_scenes):
                scene = existing_scenes[order]
                scene.narrative_excerpt = scene_data["narrative_excerpt"]
                scene.image_prompt = scene_data["image_prompt"]
            else:
                scene = Scene(
                    project_id=project.id,
                    scene_order=order,
                    narrative_excerpt=scene_data["narrative_excerpt"],
                    image_prompt=scene_data["image_prompt"],
                )
                db.add(scene)
            db.flush()
            img = _generate_scene_image(db, project, scene, order, out_dir)
            if order == 0:
                first_image = img
        for extra in existing_scenes[len(scene_prompts) :]:
            db.delete(extra)
    else:
        db.query(Scene).filter(Scene.project_id == project.id).delete()
        for order, scene_data in enumerate(scene_prompts):
            scene = Scene(
                project_id=project.id,
                scene_order=order,
                narrative_excerpt=scene_data["narrative_excerpt"],
                image_prompt=scene_data["image_prompt"],
            )
            db.add(scene)
            db.flush()
            img = _generate_scene_image(db, project, scene, order, out_dir)
            if order == 0:
                first_image = img

    # Thumbnail = first scene image (no extra Replicate call)
    if first_image:
        first_image.is_thumbnail = True
        project.thumbnail_path = first_image.file_path

    script_h = hash_script(project.script_text)
    project.script_hash = script_h
    project.images_script_hash = script_h
    project.status = ProjectStatus.IMAGES_READY
    db.commit()
    db.refresh(project)
    return project
