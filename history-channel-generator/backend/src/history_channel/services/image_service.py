from pathlib import Path

from sqlalchemy.orm import Session

from history_channel.agents.image_prompt_agent import generate_scene_prompts
from history_channel.config import settings
from history_channel.models import GeneratedImage, ProjectStatus, ProjectTopic, Scene
from history_channel.providers.factory import get_image_provider
from history_channel.providers.types import ImageGenerationRequest


def _generate_scene_image(
    db: Session,
    project: ProjectTopic,
    scene: Scene,
    order: int,
    out_dir: Path,
) -> GeneratedImage:
    """Generate exactly one image per scene and auto-select it."""
    provider = get_image_provider()
    file_path = out_dir / f"scene_{order}.png"
    request = ImageGenerationRequest(
        prompt=scene.image_prompt or "",
        negative_prompt=settings.flux_negative_prompt,
        aspect_ratio="16:9",
    )
    provider.generate_to_file(request, file_path)

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


def generate_test_image(
    prompt: str,
    *,
    width: int | None = None,
    height: int | None = None,
    seed: int | None = None,
) -> dict:
    """Generate a one-off test image for the Image Test UI."""
    from datetime import datetime, timezone

    provider = get_image_provider()
    out_dir = settings.test_images_output_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"test_{stamp}.png"
    if seed is not None:
        filename = f"test_{stamp}_seed{seed}.png"
    dest = out_dir / filename

    request = ImageGenerationRequest(
        prompt=prompt,
        width=width,
        height=height,
        seed=seed,
        negative_prompt=settings.flux_negative_prompt,
        aspect_ratio="16:9",
    )
    result = provider.generate_to_file(request, dest)
    resolved_width = width or settings.comfyui_default_width
    resolved_height = height or settings.comfyui_default_height

    return {
        "message": "Test image generated successfully",
        "provider": provider.name,
        "file_path": str(dest),
        "media_url": f"/media/test_images/{filename}",
        "generation_time_sec": result.generation_time_sec,
        "width": resolved_width,
        "height": resolved_height,
        "seed": result.seed,
    }
