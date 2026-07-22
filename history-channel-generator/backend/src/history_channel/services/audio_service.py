"""Audio generation with paragraph-level TTS reuse for small script edits."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import httpx
from openai import OpenAI
from sqlalchemy.orm import Session

from history_channel.config import settings
from history_channel.models import ProjectStatus, ProjectTopic, Scene
from history_channel.readiness import hash_script


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def split_paragraphs(text: str) -> list[str]:
    """Split script into paragraphs (blank lines) or sentence groups as fallback."""
    raw = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if len(raw) >= 2:
        return raw
    # Fallback: groups of ~3 sentences for stitch granularity
    sentences = _split_sentences(text)
    if not sentences:
        return [text.strip()] if text.strip() else []
    groups: list[str] = []
    for i in range(0, len(sentences), 3):
        groups.append(" ".join(sentences[i : i + 3]))
    return groups


def _para_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _manifest_path(project_id: int) -> Path:
    return settings.project_output_dir(project_id) / "audio" / "manifest.json"


def _paragraphs_dir(project_id: int) -> Path:
    path = settings.project_output_dir(project_id) / "audio" / "paragraphs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_manifest(project_id: int) -> list[dict]:
    path = _manifest_path(project_id)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_manifest(project_id: int, entries: list[dict]) -> None:
    path = _manifest_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _tts_paragraph(text: str) -> bytes:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.content


def _concat_mp3_files(paths: list[Path], dest: Path) -> None:
    """Naive MP3 concatenation (works for same-encoder ElevenLabs frames)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as out:
        for p in paths:
            out.write(p.read_bytes())


def _assign_scene_timings(
    scenes_data: list[dict],
    segments: list[dict],
    total_duration: float,
) -> list[dict]:
    if not segments:
        duration_each = total_duration / max(len(scenes_data), 1)
        result = []
        t = 0.0
        for scene in scenes_data:
            result.append({**scene, "start_time": t, "end_time": t + duration_each})
            t += duration_each
        return result

    seg_texts = [s.get("text", "").strip().lower() for s in segments]
    seg_starts = [float(s.get("start", 0)) for s in segments]
    seg_ends = [float(s.get("end", 0)) for s in segments]

    result = []
    seg_idx = 0
    for scene in scenes_data:
        excerpt = scene["narrative_excerpt"].lower()
        words = excerpt.split()[:5]
        start_time = seg_starts[seg_idx] if seg_idx < len(seg_starts) else 0.0
        end_time = seg_ends[-1]

        for i in range(seg_idx, len(seg_texts)):
            if any(w in seg_texts[i] for w in words if len(w) > 3):
                start_time = seg_starts[i]
                seg_idx = i
                break

        end_idx = min(
            seg_idx + max(1, len(segments) // max(len(scenes_data), 1)),
            len(seg_ends) - 1,
        )
        end_time = seg_ends[end_idx]
        seg_idx = min(end_idx + 1, len(seg_ends) - 1)
        result.append({**scene, "start_time": start_time, "end_time": end_time})

    return result


def _build_scenes_from_whisper(
    db: Session, project: ProjectTopic, ts_data: dict
) -> None:
    """Refresh scene timing rows from script + whisper (preserve image prompts if possible)."""
    sentences = _split_sentences(project.script_text or "")
    min_scenes, max_scenes = settings.scene_count_range(project.is_test_mode)
    target_scenes = min(max_scenes, max(min_scenes, len(sentences) or 1))

    per_scene = max(1, len(sentences) // target_scenes) if sentences else 1
    scene_excerpts = []
    for i in range(0, max(len(sentences), 1), per_scene):
        chunk = " ".join(sentences[i : i + per_scene]) if sentences else (project.script_text or "")
        scene_excerpts.append({"narrative_excerpt": chunk, "image_prompt": None})

    segments = ts_data.get("segments", [])
    duration = float(
        ts_data.get("duration", segments[-1]["end"] if segments else 60.0)
    )
    timed_scenes = _assign_scene_timings(scene_excerpts, segments, duration)

    existing = (
        db.query(Scene)
        .filter(Scene.project_id == project.id)
        .order_by(Scene.scene_order.asc())
        .all()
    )
    # Preserve image prompts / selected images when scene count matches
    if existing and len(existing) == len(timed_scenes):
        for scene, data in zip(existing, timed_scenes):
            scene.narrative_excerpt = data["narrative_excerpt"]
            scene.start_time = data.get("start_time")
            scene.end_time = data.get("end_time")
    else:
        db.query(Scene).filter(Scene.project_id == project.id).delete()
        for order, scene_data in enumerate(timed_scenes):
            db.add(
                Scene(
                    project_id=project.id,
                    scene_order=order,
                    narrative_excerpt=scene_data["narrative_excerpt"],
                    image_prompt=None,
                    start_time=scene_data.get("start_time"),
                    end_time=scene_data.get("end_time"),
                )
            )


def generate_audio(db: Session, project: ProjectTopic) -> tuple[ProjectTopic, int, int]:
    """
    Generate narration with paragraph-level reuse.
    Returns (project, paragraphs_reused, paragraphs_generated).
    """
    if not project.script_text:
        raise ValueError("Script must be approved before generating audio")
    if not settings.elevenlabs_api_key or not settings.elevenlabs_voice_id:
        raise ValueError("ElevenLabs API key and voice ID are required")

    paragraphs = split_paragraphs(project.script_text)
    if not paragraphs:
        raise ValueError("Script has no usable paragraphs")

    prev = _load_manifest(project.id)
    by_hash = {
        e["text_hash"]: e
        for e in prev
        if e.get("text_hash") and e.get("path")
    }

    para_dir = _paragraphs_dir(project.id)
    new_manifest: list[dict] = []
    mp3_paths: list[Path] = []
    reused = 0
    generated = 0

    for i, text in enumerate(paragraphs):
        th = _para_hash(text)
        dest = para_dir / f"para_{i}.mp3"
        reused_entry = by_hash.get(th)
        reused_path = Path(reused_entry["path"]) if reused_entry else None
        if reused_path and not reused_path.is_absolute():
            reused_path = settings.backend_root / reused_path

        if reused_path and reused_path.is_file():
            if reused_path.resolve() != dest.resolve():
                dest.write_bytes(reused_path.read_bytes())
            reused += 1
        else:
            audio_bytes = _tts_paragraph(text)
            dest.write_bytes(audio_bytes)
            generated += 1

        mp3_paths.append(dest)
        new_manifest.append(
            {
                "index": i,
                "text": text,
                "text_hash": th,
                "path": str(dest),
            }
        )

    out_dir = settings.project_output_dir(project.id)
    audio_path = out_dir / "narration.mp3"
    _concat_mp3_files(mp3_paths, audio_path)
    _save_manifest(project.id, new_manifest)

    client_openai = OpenAI(api_key=settings.openai_api_key)
    with open(audio_path, "rb") as audio_file:
        transcription = client_openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
        )

    ts_data = (
        transcription.model_dump()
        if hasattr(transcription, "model_dump")
        else dict(transcription)
    )
    project.audio_path = str(audio_path)
    project.whisper_timestamps = ts_data

    script_h = hash_script(project.script_text)
    project.script_hash = script_h
    project.audio_script_hash = script_h

    _build_scenes_from_whisper(db, project, ts_data)

    project.status = ProjectStatus.AUDIO_READY
    db.commit()
    db.refresh(project)
    return project, reused, generated
