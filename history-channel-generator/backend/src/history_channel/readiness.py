"""Asset-based readiness helpers (files + script fingerprints)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from history_channel.config import settings
from history_channel.models import ProjectTopic, Scene


def hash_script(text: str | None) -> str | None:
    if not text or not text.strip():
        return None
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _resolve(path_str: str | None) -> Path | None:
    if not path_str:
        return None
    p = Path(path_str)
    if not p.is_absolute():
        p = settings.backend_root / path_str
    return p


def file_exists(path_str: str | None) -> bool:
    p = _resolve(path_str)
    return bool(p and p.is_file())


def has_script(project: ProjectTopic) -> bool:
    return bool(project.script_text and len(project.script_text.strip()) >= 50)


def has_audio(project: ProjectTopic) -> bool:
    return (
        has_script(project)
        and file_exists(project.audio_path)
        and bool(project.whisper_timestamps)
    )


def has_images(project: ProjectTopic) -> bool:
    """True if every scene has at least one image file (selected or first variation)."""
    scenes = list(project.scenes or [])
    if not scenes:
        # Fallback: any project-level generated images on disk
        images = list(project.images or [])
        non_thumb = [img for img in images if not img.is_thumbnail]
        return any(file_exists(img.file_path) for img in non_thumb)

    for scene in scenes:
        images = list(scene.images or [])
        selected = next(
            (img for img in images if img.id == scene.selected_image_id),
            None,
        )
        candidate = selected or (images[0] if images else None)
        if not candidate or not file_exists(candidate.file_path):
            return False
    return True


def has_video(project: ProjectTopic) -> bool:
    return file_exists(project.video_path)


def audio_stale(project: ProjectTopic) -> bool:
    if not has_audio(project):
        return False
    current = project.script_hash or hash_script(project.script_text)
    return bool(current and project.audio_script_hash and current != project.audio_script_hash)


def images_stale(project: ProjectTopic) -> bool:
    if not has_images(project):
        return False
    current = project.script_hash or hash_script(project.script_text)
    return bool(current and project.images_script_hash and current != project.images_script_hash)


def can_generate_audio(project: ProjectTopic) -> bool:
    return has_script(project)


def can_generate_images(project: ProjectTopic) -> bool:
    return has_audio(project)


def can_generate_video(project: ProjectTopic) -> bool:
    return has_audio(project) and has_images(project) and not audio_stale(project)


def pipeline_warnings(project: ProjectTopic) -> list[str]:
    warnings: list[str] = []
    if audio_stale(project):
        warnings.append(
            "Script changed since audio was generated — regenerate audio before video (required)."
        )
    if images_stale(project):
        warnings.append(
            "Script changed since images were generated — regenerating images is recommended."
        )
    if has_script(project) and not has_audio(project):
        warnings.append("No audio yet — generate audio to continue.")
    if has_audio(project) and not has_images(project):
        warnings.append("No images yet — generate images before video.")
    return warnings


def sync_status_from_assets(project: ProjectTopic) -> None:
    """Advance status enum to match existing artifacts (UI stepper only)."""
    from history_channel.models import ProjectStatus

    if has_video(project) and not audio_stale(project) and has_images(project):
        project.status = ProjectStatus.VIDEO_READY
    elif has_images(project):
        project.status = ProjectStatus.IMAGES_READY
    elif has_audio(project):
        project.status = ProjectStatus.AUDIO_READY
    elif has_script(project):
        project.status = ProjectStatus.SCRIPT_READY
