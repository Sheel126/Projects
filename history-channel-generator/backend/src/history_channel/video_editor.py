"""
Masterclass cinematic video assembly engine.

Primary entry point:
    generate_documentary(
        project_id, image_mappings, voice_audio_path,
        whisper_timestamps, is_test_mode,
    ) -> str

Assets (under backend/assets/, snake_case):
    overlays/film_grain_loop.mp4
    overlays/dust_particles.mp4
    overlays/film_scratches.mp4
    audio/music/suspense_background.mp3

- 720p @ 24fps in test mode (truncated to first 3 transitions),
  1080p @ 30fps in production.
- Ken Burns motion unified on a symmetric cubic S-curve (`ease_in_out_cubic`):
  every scene enters and exits at zero velocity, so cuts and crossfades
  never carry a velocity spike. No shake / no handheld jitter.
- Gentle zoom (≤10%) and half-length pan sweeps so nothing races across
  the frame. Optional micro-sway is off by default.
- 5.5s jump-cut zoom pacing anchored to Whisper word boundaries, with a
  soft +8% re-frame boost (down from the old +15% punch).
- Atmospheric overlays (film grain + dust particles) at 6% opacity.
- Sound design: a single suspense-music bed under narration at all times,
  with smooth climactic swells at each paragraph/chapter start and a
  gentle boost during narrator silences. No punctuation SFX.
- Soft fade-in on open and 2s cinematic fade-out at close (video + audio).

The ORM-facing helper `render_video(project, scenes)` builds
`image_mappings` from the SQLAlchemy models and delegates here, so the
FastAPI service and version archiver keep working unchanged.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


def _iso_utc(dt: datetime | None = None) -> str:
    """ECMAScript-safe ISO 8601 UTC timestamp with millisecond precision.

    Produces strings like ``2026-07-20T13:43:42.637Z`` — parsed correctly by
    every modern browser. Chrome/Edge on Windows can misparse 6-digit
    microseconds + ``+00:00`` offset and drift by the local UTC offset.
    """
    dt = (dt or datetime.now(timezone.utc)).astimezone(timezone.utc)
    ms = dt.microsecond // 1000
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms:03d}Z"


from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_audioclips,
    concatenate_videoclips,
)
from moviepy.audio.AudioClip import AudioClip
from moviepy.audio.fx import AudioFadeIn, AudioFadeOut
from moviepy.video.fx import FadeIn, FadeOut

import numpy as np

from history_channel.config import settings
from history_channel.models import ProjectTopic, Scene

ProgressCallback = Callable[[str], None]

# ---------------------------------------------------------------------------
# Cinematic constants
# ---------------------------------------------------------------------------
JUMP_CUT_THRESHOLD = 5.5           # sec — clips longer than this get sliced
JUMP_CUT_SCALE_BOOST = 0.08        # +8% zoom on jump-cut half (subtle re-frame)
CROSSFADE_SCENE = 0.4              # sec — soft dissolve between new images
OVERLAY_OPACITY = 0.06             # grain + dust
SCRATCH_OPACITY = 0.05             # scratches (subtler)
# Sway is disabled — the eased Ken Burns curve alone provides all the
# organic movement the frame needs. Constants preserved for future opt-in.
MICRO_SHAKE_AMP = 0.0              # 0 = perfectly stable frame
MICRO_SHAKE_FREQ_X = 0.09          # Hz (unused while amplitude = 0)
MICRO_SHAKE_FREQ_Y = 0.07          # Hz (unused while amplitude = 0)

# --- Music bed levels (single continuous track, no punctuation SFX) ---
# Tuned so music never overpowers the narrator. Peak stays ~7 dB above the
# baseline for a clear "swell", but the whole track sits 4–5 dB below what
# it used to; the narrator now cuts through even in busy sections.
MUSIC_BASE_DB = -22.0              # quiet, present bed (≈0.079 linear)
MUSIC_SWELL_PEAK_DB = -15.0        # climactic swell peak (≈0.178 linear)
MUSIC_SILENCE_BOOST_DB = 5.0       # +5 dB above baseline during narrator gaps
SWELL_ATTACK_SEC = 0.9             # rise time from baseline → peak
SWELL_HOLD_SEC = 1.2               # plateau at peak
SWELL_DECAY_SEC = 3.2              # gentle release back to baseline
SWELL_LEAD_SEC = 0.25              # start swell a hair before the paragraph
SWELL_SKIP_HEAD_SEC = 3.0          # don't swell within opening fade-in window
SILENCE_GAP_SEC = 0.6              # narrator gap ≥ this = eligible for boost

# --- Opening/closing transitions ---
FADE_IN_SEC = 0.7                  # soft open (video + audio)
FADE_OUT_SEC = 2.0                 # cinematic close (video + audio)

# Canvas geometry
FPS_TEST = 24
FPS_PROD = 30
TEST_MODE_MAX_TRANSITIONS = 3
RES_TEST = (1280, 720)
RES_PROD = (1920, 1080)


class MotionProfile(str, Enum):
    """Motion matrix. Zoom-in/out are the required cubic ease-out curves;
    pan/dolly variants keep the timeline visually varied under the same
    cubic/quad easing family."""

    ZOOM_IN = "zoom_in"       # Cubic Ease-Out Scale  (spec §3)
    ZOOM_OUT = "zoom_out"     # Cubic Ease-Out Contract (spec §3)
    PAN_LTR = "pan_ltr"
    PAN_RTL = "pan_rtl"
    DOLLY = "dolly"


@dataclass
class ImageSegment:
    image_path: Path
    duration: float
    start_on_timeline: float
    profile: MotionProfile
    is_jump_cut: bool = False
    scale_boost: float = 0.0
    reverse_motion: bool = False
    is_new_asset: bool = True
    scene_index: int = 0


# ---------------------------------------------------------------------------
# Path / asset resolution
# ---------------------------------------------------------------------------
def _resolve_path(path_str: str | Path) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else settings.backend_root / path_str


def _assets_root() -> Path:
    return settings.backend_root / "assets"


# Canonical asset paths under backend/assets/ (snake_case, no spaces)
ASSET_FILM_GRAIN = "overlays/film_grain_loop.mp4"
ASSET_DUST = "overlays/dust_particles.mp4"
ASSET_SCRATCHES = "overlays/film_scratches.mp4"
ASSET_MUSIC = "audio/music/suspense_background.mp3"


def _require_asset(relative: str) -> Path:
    """Resolve a required asset under backend/assets/. Raises if missing."""
    path = _assets_root() / relative
    if not path.is_file():
        raise FileNotFoundError(
            f"Required cinematic asset missing: {path}. "
            f"Expected under backend/assets/{relative}"
        )
    return path


def _optional_asset(relative: str) -> Path | None:
    path = _assets_root() / relative
    return path if path.is_file() else None


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------
def ease_out_cubic(t: float) -> float:
    """S(t) = 1 - (1 - t)^3  — decelerating cubic ease-out."""
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    """Symmetric cubic S-curve — slow start, glide through middle, slow stop.

    This is the workhorse easing for the entire timeline: no velocity spike
    at scene boundaries (unlike ease_out_cubic which hits max velocity at
    t=0), and gentler mid-scene acceleration than ease_in_out_quad. Ken
    Burns motion built on this curve reads as a smooth camera glide, not
    a lurching pan.
    """
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


def ease_in_out_quad(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2


def db_to_linear(db: float) -> float:
    return 10 ** (db / 20.0)


def _silence(duration: float) -> AudioClip:
    return AudioClip(lambda t: 0, duration=max(duration, 0.01), fps=44100)


def _pick_profile(seed: int) -> MotionProfile:
    profiles = list(MotionProfile)
    return profiles[seed % len(profiles)]


def _reversed_profile(profile: MotionProfile) -> MotionProfile:
    return {
        MotionProfile.ZOOM_IN: MotionProfile.ZOOM_OUT,
        MotionProfile.ZOOM_OUT: MotionProfile.ZOOM_IN,
        MotionProfile.PAN_LTR: MotionProfile.PAN_RTL,
        MotionProfile.PAN_RTL: MotionProfile.PAN_LTR,
        MotionProfile.DOLLY: MotionProfile.ZOOM_IN,
    }[profile]


# ---------------------------------------------------------------------------
# Whisper analysis (word boundaries + narrator silence detection)
# ---------------------------------------------------------------------------
def _extract_words(whisper: dict | None) -> list[dict]:
    if not whisper:
        return []
    words = whisper.get("words")
    if isinstance(words, list) and words:
        return words
    out: list[dict] = []
    for seg in whisper.get("segments") or []:
        seg_words = seg.get("words")
        if isinstance(seg_words, list):
            out.extend(seg_words)
        else:
            out.append(
                {
                    "start": float(seg.get("start", 0)),
                    "end": float(seg.get("end", 0)),
                    "word": seg.get("text", ""),
                }
            )
    return out


def _word_boundary_split(start: float, end: float, words: list[dict]) -> float:
    """Return a word boundary within [start+0.8, end-0.8] closest to midpoint."""
    mid = (start + end) / 2.0
    if not words:
        return mid
    best = mid
    best_dist = abs(end - start)
    for w in words:
        t = float(w.get("start", mid))
        if start + 0.8 < t < end - 0.8:
            dist = abs(t - mid)
            if dist < best_dist:
                best = t
                best_dist = dist
    return best


def _silence_windows(
    whisper: dict | None, total: float
) -> list[tuple[float, float]]:
    """Find narrator silences ≥ SILENCE_GAP_SEC by walking word ends."""
    words = _extract_words(whisper)
    if not words:
        return []
    events = sorted(float(w.get("end", w.get("start", 0))) for w in words)
    windows: list[tuple[float, float]] = []
    prev = 0.0
    for t in events:
        if t - prev >= SILENCE_GAP_SEC:
            windows.append((prev, t))
        prev = max(prev, t)
    if total - prev >= SILENCE_GAP_SEC:
        windows.append((prev, total))
    return windows


# ---------------------------------------------------------------------------
# Segment planning (image_mappings → ImageSegment list w/ jump cuts)
# ---------------------------------------------------------------------------
def _normalize_mappings(
    image_mappings: list[dict], voice_duration: float
) -> list[dict]:
    """Fill missing start/end times and clip to voice duration."""
    if not image_mappings:
        return []

    normalized: list[dict] = []
    fallback_span = voice_duration / max(len(image_mappings), 1)
    cursor = 0.0
    for i, m in enumerate(image_mappings):
        start = m.get("start_time")
        end = m.get("end_time")
        if start is None:
            start = cursor
        if end is None:
            end = float(start) + fallback_span
        start = max(0.0, float(start))
        end = max(start + 0.05, float(end))
        normalized.append(
            {
                "image_path": _resolve_path(m["image_path"]),
                "start_time": start,
                "end_time": end,
                "scene_index": int(m.get("scene_index", i)),
                "is_paragraph_start": bool(m.get("is_paragraph_start", i == 0)),
            }
        )
        cursor = end
    return normalized


def _build_segments(
    mappings: list[dict], words: list[dict]
) -> list[ImageSegment]:
    """Convert image mappings into ordered ImageSegment plans, slicing any
    span longer than JUMP_CUT_THRESHOLD at the closest Whisper word boundary
    into (motion + jump-cut zoom) halves.
    """
    segments: list[ImageSegment] = []
    timeline = 0.0
    for m in mappings:
        duration = max(m["end_time"] - m["start_time"], 0.05)
        profile = _pick_profile(m["scene_index"])
        start_ref = float(m["start_time"])
        end_ref = start_ref + duration

        if duration > JUMP_CUT_THRESHOLD:
            split_abs = _word_boundary_split(start_ref, end_ref, words)
            d1 = max(split_abs - start_ref, 0.8)
            d2 = max(duration - d1, 0.8)
            if d1 + d2 > duration + 0.05:
                d2 = duration - d1
            segments.append(
                ImageSegment(
                    image_path=m["image_path"],
                    duration=d1,
                    start_on_timeline=timeline,
                    profile=profile,
                    is_new_asset=True,
                    scene_index=m["scene_index"],
                )
            )
            segments.append(
                ImageSegment(
                    image_path=m["image_path"],
                    duration=d2,
                    start_on_timeline=timeline + d1,
                    profile=_reversed_profile(profile),
                    is_jump_cut=True,
                    scale_boost=JUMP_CUT_SCALE_BOOST,
                    reverse_motion=True,
                    is_new_asset=False,
                    scene_index=m["scene_index"],
                )
            )
        else:
            segments.append(
                ImageSegment(
                    image_path=m["image_path"],
                    duration=duration,
                    start_on_timeline=timeline,
                    profile=profile,
                    is_new_asset=True,
                    scene_index=m["scene_index"],
                )
            )
        timeline += duration
    return segments


# ---------------------------------------------------------------------------
# Eased Ken Burns — smooth cinematic glide
# ---------------------------------------------------------------------------
def _ken_burns_clip(
    seg: ImageSegment, width: int, height: int
) -> CompositeVideoClip:
    """Smooth eased Ken Burns motion — no shake, no punch at scene starts.

    Every profile uses a symmetric cubic ease so the camera enters and
    exits each scene at zero velocity, then glides through the middle.
    Zooms are gentle (≤10%) and pan sweeps are half what they used to be
    so nothing races across the frame.

    Extra +boost applies on jump-cut halves. Image is pre-scaled once to
    the max cover size so the animated resize is always a bounded downscale.
    """
    duration = max(seg.duration, 0.05)
    boost = seg.scale_boost
    ease = ease_in_out_cubic  # unified — no lurching handoff between profiles

    if seg.profile == MotionProfile.ZOOM_IN:
        s_start, s_end = 1.00 + boost, 1.10 + boost
        pan_start, pan_end = (-0.02, -0.01), (0.02, 0.01)
    elif seg.profile == MotionProfile.ZOOM_OUT:
        s_start, s_end = 1.10 + boost, 1.00 + boost
        pan_start, pan_end = (0.02, 0.01), (-0.02, -0.01)
    elif seg.profile == MotionProfile.PAN_LTR:
        s_start, s_end = 1.10 + boost, 1.11 + boost
        pan_start, pan_end = (-0.15, -0.02), (0.15, 0.02)
    elif seg.profile == MotionProfile.PAN_RTL:
        s_start, s_end = 1.10 + boost, 1.11 + boost
        pan_start, pan_end = (0.15, 0.02), (-0.15, -0.02)
    else:  # DOLLY — gentle push-in with subtle Y-tilt
        s_start, s_end = 1.05 + boost, 1.12 + boost
        pan_start, pan_end = (-0.03, -0.06), (0.03, 0.06)

    if seg.reverse_motion:
        s_start, s_end = s_end, s_start
        pan_start, pan_end = pan_end, pan_start

    max_scale = max(s_start, s_end) * 1.02
    img = ImageClip(str(seg.image_path)).with_duration(duration)
    cover_h = int(height * max_scale)
    cover_w = int(width * max_scale)
    img = img.resized(height=cover_h)
    if img.w < cover_w:
        img = img.resized(width=cover_w)
    base_w, base_h = float(img.w), float(img.h)

    rel_start = s_start / max_scale
    rel_end = s_end / max_scale
    delta_rel = rel_end - rel_start
    dx = pan_end[0] - pan_start[0]
    dy = pan_end[1] - pan_start[1]

    def scale_factor(t: float) -> float:
        return rel_start + delta_rel * ease(t / duration)

    img = img.resized(lambda t: scale_factor(t))

    shake_x = MICRO_SHAKE_AMP * width
    shake_y = MICRO_SHAKE_AMP * height
    apply_sway = shake_x > 0 or shake_y > 0

    def position(t: float):
        p = ease(t / duration)
        rel = rel_start + delta_rel * p
        cur_w = base_w * rel
        cur_h = base_h * rel
        overflow_x = max(0.0, cur_w - width)
        overflow_y = max(0.0, cur_h - height)
        x = -overflow_x / 2.0 + (pan_start[0] + dx * p) * overflow_x
        y = -overflow_y / 2.0 + (pan_start[1] + dy * p) * overflow_y
        # Sway is off by default; only kick in if opted-in via MICRO_SHAKE_AMP
        if apply_sway:
            x += math.sin(2 * math.pi * MICRO_SHAKE_FREQ_X * t) * shake_x
            y += math.cos(2 * math.pi * MICRO_SHAKE_FREQ_Y * t) * shake_y
        return (x, y)

    bg = ColorClip(size=(width, height), color=(0, 0, 0)).with_duration(duration)
    return CompositeVideoClip(
        [bg, img.with_position(position)], size=(width, height)
    ).with_duration(duration)


# ---------------------------------------------------------------------------
# Overlay loop helper
# ---------------------------------------------------------------------------
def _loop_video(
    path: Path, duration: float, width: int, height: int, opacity: float
):
    clip = VideoFileClip(str(path), audio=False)
    clip = clip.resized(new_size=(width, height))
    if clip.duration < duration:
        loops = int(duration / max(clip.duration, 0.01)) + 1
        clip = concatenate_videoclips([clip] * loops, method="compose")
    clip = clip.subclipped(0, duration)
    if hasattr(clip, "with_opacity"):
        clip = clip.with_opacity(opacity)
    return clip


# ---------------------------------------------------------------------------
# Continuous music bed: baseline + climactic swells + silence boost
# ---------------------------------------------------------------------------
def _smoothstep(x: np.ndarray) -> np.ndarray:
    """Cubic Hermite smoothstep — S-curve on [0, 1] (0→0, 1→1, smooth ends)."""
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _build_music_bed(
    music_path: Path,
    duration: float,
    swell_times: list[float],
    silence_windows: list[tuple[float, float]],
) -> AudioClip:
    """Suspense music that plays throughout at a warm baseline volume,
    with smooth climactic swells at each ``swell_times`` marker (paragraph /
    chapter starts) and a small boost during long narrator silences.

    Curve shape per swell:
        t < 0                             : baseline
        0 ≤ t < ATTACK                    : baseline → peak (smoothstep)
        ATTACK ≤ t < ATTACK+HOLD          : peak plateau
        ATTACK+HOLD ≤ t < ATTACK+HOLD+DECAY : peak → baseline (smoothstep)

    Overlapping regions take the LOUDER value (np.maximum) so a swell
    never accidentally silences a boost, and vice versa.
    """
    music = AudioFileClip(str(music_path))
    if music.duration < duration:
        loops = int(duration / music.duration) + 1
        music = concatenate_audioclips([music] * loops)
    music = music.subclipped(0, duration)

    baseline = db_to_linear(MUSIC_BASE_DB)
    peak = db_to_linear(MUSIC_SWELL_PEAK_DB)
    boost = db_to_linear(MUSIC_BASE_DB + MUSIC_SILENCE_BOOST_DB)

    # Reject swells that would trigger inside the opening fade-in window
    active_swells = np.array(
        sorted(s for s in swell_times if s >= SWELL_SKIP_HEAD_SEC),
        dtype=np.float64,
    )
    silence_arr = (
        np.array(silence_windows, dtype=np.float64)
        if silence_windows
        else np.empty((0, 2), dtype=np.float64)
    )

    swell_total = SWELL_ATTACK_SEC + SWELL_HOLD_SEC + SWELL_DECAY_SEC

    def envelope(t_arr: np.ndarray) -> np.ndarray:
        t = np.asarray(t_arr, dtype=np.float64)
        g = np.full(t.shape, baseline, dtype=np.float64)

        # Silence boost — soft feathered edges so the level change is inaudible
        if silence_arr.size:
            feather = 0.25
            for a, b in silence_arr:
                # Weight goes 0→1 across [a-feather, a+feather] and back over [b-feather, b+feather]
                w = np.clip((t - (a - feather)) / (2 * feather), 0.0, 1.0) - np.clip(
                    (t - (b - feather)) / (2 * feather), 0.0, 1.0
                )
                w = _smoothstep(w)
                lvl = baseline + (boost - baseline) * w
                g = np.maximum(g, lvl)

        # Climactic music swells at chapter starts
        for start in active_swells:
            dt = t - (start - SWELL_LEAD_SEC)
            lvl = np.full(t.shape, baseline, dtype=np.float64)

            m_atk = (dt >= 0.0) & (dt < SWELL_ATTACK_SEC)
            if m_atk.any():
                x = _smoothstep(dt / SWELL_ATTACK_SEC)
                lvl = np.where(m_atk, baseline + (peak - baseline) * x, lvl)

            m_hold = (dt >= SWELL_ATTACK_SEC) & (
                dt < SWELL_ATTACK_SEC + SWELL_HOLD_SEC
            )
            lvl = np.where(m_hold, peak, lvl)

            m_dec = (dt >= SWELL_ATTACK_SEC + SWELL_HOLD_SEC) & (dt < swell_total)
            if m_dec.any():
                x = _smoothstep(
                    (dt - SWELL_ATTACK_SEC - SWELL_HOLD_SEC) / SWELL_DECAY_SEC
                )
                lvl = np.where(m_dec, peak + (baseline - peak) * x, lvl)

            g = np.maximum(g, lvl)

        return g

    def transform(get_frame, t):
        frame = np.asarray(get_frame(t))
        t_arr = np.atleast_1d(np.asarray(t, dtype=np.float64))
        gains = envelope(t_arr)
        # Restore scalar case
        if np.ndim(t) == 0:
            return frame * float(gains[0])
        if frame.ndim == 2:
            return frame * gains[:, None]
        return frame * gains

    return music.transform(transform, keep_duration=True)


# ---------------------------------------------------------------------------
# Video versioning
# ---------------------------------------------------------------------------
# NOTE: We do NOT overwrite or rename any prior render. Every regenerate
# writes to its own uniquely-named file under `versions/`, so a video the
# browser is currently streaming can never be locked/renamed underneath it
# (fixes Windows WinError 32 during rapid regenerates while playback is live).
def archive_previous_video(project: ProjectTopic, out_dir: Path) -> list[dict]:
    """Backwards-compatible no-op — historical renders are never moved.

    Legacy projects may still have a bare ``final.mp4`` on disk; that file
    remains referenced by its DB row (created by ``backfill_video_versions``).
    """
    del out_dir  # unused; kept for signature compatibility
    return [dict(v) for v in (project.video_versions or [])]


def _next_render_output(project: ProjectTopic, out_dir: Path) -> Path:
    """Return a unique output path for the next render.

    Layout: ``output/<project_id>/versions/render_<N>_<UTC_stamp>.mp4``
    """
    versions = list(project.video_versions or [])
    next_num = len(versions) + 1
    versions_dir = out_dir / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return versions_dir / f"render_{next_num}_{stamp}.mp4"


def append_video_version(
    versions: list[dict] | None, video_path: Path | str
) -> list[dict]:
    """Append a freshly encoded render to the permanent history list."""
    history: list[dict] = [dict(v) for v in (versions or [])]
    history.append(
        {
            "path": str(video_path),
            "label": f"Render {len(history) + 1}",
            "created_at": _iso_utc(),
        }
    )
    # Keep a long history so users can compare many regenerations
    return history[-50:]


def backfill_video_versions(project: ProjectTopic) -> bool:
    """Ensure legacy projects (rendered before versioning existed) show up
    in the UI history as ``Render 1``.

    Returns ``True`` if the project's ``video_versions`` was mutated so the
    caller can commit the change.
    """
    if project.video_versions:
        return False
    if not project.video_path:
        return False

    video_path = _resolve_path(project.video_path)
    if not video_path.is_file():
        return False

    # Use file mtime as the render timestamp (best available proxy)
    try:
        mtime = _iso_utc(
            datetime.fromtimestamp(video_path.stat().st_mtime, tz=timezone.utc)
        )
    except OSError:
        mtime = _iso_utc()

    project.video_versions = [
        {
            "path": str(video_path),
            "label": "Render 1",
            "created_at": mtime,
        }
    ]
    return True


# ---------------------------------------------------------------------------
# Primary entry point (spec §2)
# ---------------------------------------------------------------------------
def generate_documentary(
    project_id: str,
    image_mappings: list[dict],
    voice_audio_path: str,
    whisper_timestamps: dict,
    is_test_mode: bool,
    on_progress: ProgressCallback | None = None,
    output_path: str | Path | None = None,
) -> str:
    """Build a cinematic MP4 from primitive inputs and return its full path.

    image_mappings entries: {image_path, start_time, end_time, scene_index,
    is_paragraph_start}. Test mode renders 720p@24 truncated to the first
    3 transitions; production renders 1080p@30 across the full timeline.

    If ``output_path`` is omitted, writes to ``<project_output_dir>/final.mp4``
    (legacy behaviour). Callers with a versioning scheme should pass an
    explicit path — the ORM adapter `render_video` does this.
    """

    def progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    if not image_mappings:
        raise ValueError("image_mappings must not be empty")
    if not voice_audio_path:
        raise ValueError("voice_audio_path is required")

    voice_path = _resolve_path(voice_audio_path)
    if not voice_path.exists():
        raise ValueError(f"Voice audio not found: {voice_path}")

    width, height = RES_TEST if is_test_mode else RES_PROD
    fps = FPS_TEST if is_test_mode else FPS_PROD
    if is_test_mode:
        image_mappings = image_mappings[:TEST_MODE_MAX_TRANSITIONS]

    try:
        pid = int(project_id)
        out_dir = settings.project_output_dir(pid)
    except (TypeError, ValueError):
        out_dir = settings.output_dir / str(project_id)
        out_dir.mkdir(parents=True, exist_ok=True)

    pad = settings.video_end_padding_sec

    progress("Loading narration and planning camera moves…")
    narration = AudioFileClip(str(voice_path))
    total_audio = float(narration.duration)
    words = _extract_words(whisper_timestamps)

    mappings = _normalize_mappings(image_mappings, total_audio)
    # Rescale mapping spans so the last image ends at end of narration
    raw_sum = sum(m["end_time"] - m["start_time"] for m in mappings) or 1.0
    scale = total_audio / raw_sum
    for m in mappings:
        span = (m["end_time"] - m["start_time"]) * scale
        m["end_time"] = m["start_time"] + span
    # Chain start_times so the timeline is contiguous
    cursor = 0.0
    for m in mappings:
        span = m["end_time"] - m["start_time"]
        m["start_time"] = cursor
        m["end_time"] = cursor + span
        cursor = m["end_time"]

    segments = _build_segments(mappings, words)

    # ---- Video layer: eased Ken Burns clips + selective crossfade ----
    clips: list = []
    hard_cut_after: set[int] = set()
    for idx, seg in enumerate(segments):
        progress(
            f"Camera motion {idx + 1}/{len(segments)} "
            f"({seg.profile.value}{' + jump-cut' if seg.is_jump_cut else ''})…"
        )
        clips.append(_ken_burns_clip(seg, width, height))
        if seg.is_jump_cut:
            hard_cut_after.add(idx - 1)

    progress("Assembling timeline with cross-dissolves…")
    if len(clips) == 1:
        video = clips[0]
    else:
        assembled = [clips[0]]
        for i in range(1, len(clips)):
            prev_hard = (i - 1) in hard_cut_after
            if prev_hard or CROSSFADE_SCENE <= 0:
                assembled.append(clips[i])
            else:
                fade = min(
                    CROSSFADE_SCENE,
                    assembled[-1].duration / 3,
                    clips[i].duration / 3,
                )
                assembled[-1] = concatenate_videoclips(
                    [assembled[-1], clips[i]],
                    method="compose",
                    padding=-fade,
                )
        video = (
            assembled[0]
            if len(assembled) == 1
            else concatenate_videoclips(assembled, method="compose")
        )

    # Sync video length to narration (or truncated test slice)
    target_visual_duration = min(video.duration, total_audio) if is_test_mode else total_audio
    if video.duration < target_visual_duration - 0.05:
        hold = target_visual_duration - video.duration
        freeze = video.to_ImageClip(
            t=max(0, video.duration - 0.04)
        ).with_duration(hold)
        video = concatenate_videoclips([video, freeze], method="compose")
    elif video.duration > target_visual_duration + 0.05:
        video = video.subclipped(0, target_visual_duration)

    if pad > 0:
        freeze = video.to_ImageClip(
            t=max(0, video.duration - 0.04)
        ).with_duration(pad)
        video = concatenate_videoclips([video, freeze], method="compose")

    # ---- Atmospheric overlays (spec §5) ----
    progress("Layering atmospheric overlays…")
    overlay_layers = [video]
    for rel, opacity in (
        (ASSET_FILM_GRAIN, OVERLAY_OPACITY),
        (ASSET_DUST, OVERLAY_OPACITY),
        (ASSET_SCRATCHES, SCRATCH_OPACITY),
    ):
        path = _require_asset(rel)
        overlay_layers.append(
            _loop_video(path, video.duration, width, height, opacity)
        )
    video = CompositeVideoClip(
        overlay_layers, size=(width, height)
    ).with_duration(video.duration)

    # ---- Audio composite: narration + continuous suspense music bed ----
    progress("Mixing narration and suspense music bed…")
    if is_test_mode:
        voice = narration.subclipped(0, target_visual_duration)
    else:
        voice = narration
    if pad > 0:
        voice = concatenate_audioclips([voice, _silence(pad)])
    audio_layers = [voice]

    music_path = _optional_asset(ASSET_MUSIC)
    if not music_path:
        configured = _resolve_path(settings.background_music_path)
        music_path = configured if configured.is_file() else None

    silence_windows = _silence_windows(
        whisper_timestamps, target_visual_duration
    )
    # Climactic swell markers = paragraph / chapter starts
    swell_times = [
        float(m["start_time"])
        for m in mappings
        if m.get("is_paragraph_start")
    ]

    if music_path and music_path.is_file():
        audio_layers.append(
            _build_music_bed(
                music_path, video.duration, swell_times, silence_windows
            )
        )

    mixed = CompositeAudioClip(audio_layers).with_duration(video.duration)
    video = video.with_audio(mixed)

    # ---- Cinematic open + close: soft fade-in and 2s fade-out ----
    fade_in = min(FADE_IN_SEC, video.duration / 4.0)
    fade_out = min(FADE_OUT_SEC, video.duration / 4.0)
    effects = []
    if fade_in > 0:
        effects.extend([FadeIn(fade_in), AudioFadeIn(fade_in)])
    if fade_out > 0:
        effects.extend([FadeOut(fade_out), AudioFadeOut(fade_out)])
    if effects:
        video = video.with_effects(effects)

    output_path = Path(output_path) if output_path else out_dir / "final.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    progress(f"Encoding cinematic MP4 ({width}x{height}@{fps}fps)…")
    video.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        ffmpeg_params=["-movflags", "+faststart"],
        logger=None,
    )
    narration.close()
    video.close()
    progress("Complete")
    return str(output_path)


# ---------------------------------------------------------------------------
# ORM adapter — used by services/project_service.run_video_generation
# ---------------------------------------------------------------------------
def _paragraph_scene_indices(
    script: str | None, scene_count: int
) -> set[int]:
    """Given the full script, return the scene indices that begin a new
    paragraph. Falls back to every ~3 scenes as a "chapter" break when the
    script has no paragraph structure."""
    if scene_count <= 0:
        return set()
    if not script:
        return {0}
    paragraphs = [p.strip() for p in script.split("\n\n") if p.strip()]
    if len(paragraphs) <= 1:
        return {0, *(i for i in range(scene_count) if i > 0 and i % 3 == 0)}
    starts = {0}
    n = len(paragraphs)
    for i in range(1, n):
        starts.add(min(int(i * scene_count / n), max(scene_count - 1, 0)))
    return starts


def _image_mappings_from_scenes(
    project: ProjectTopic, scenes: list[Scene], voice_duration: float
) -> list[dict]:
    para_starts = _paragraph_scene_indices(project.script_text, len(scenes))
    fallback_span = voice_duration / max(len(scenes), 1)
    cursor = 0.0
    mappings: list[dict] = []
    for i, scene in enumerate(scenes):
        image = next(
            (img for img in scene.images if img.id == scene.selected_image_id),
            None,
        )
        if not image:
            raise ValueError(f"Scene {i + 1} has no selected image")
        start = (
            float(scene.start_time)
            if scene.start_time is not None
            else cursor
        )
        end = (
            float(scene.end_time)
            if scene.end_time is not None
            else start + fallback_span
        )
        mappings.append(
            {
                "image_path": _resolve_path(image.file_path),
                "start_time": start,
                "end_time": max(end, start + 0.05),
                "scene_index": i,
                "is_paragraph_start": i in para_starts,
            }
        )
        cursor = mappings[-1]["end_time"]
    return mappings


def render_video(
    project: ProjectTopic,
    scenes: list[Scene],
    on_progress: ProgressCallback | None = None,
) -> Path:
    """ORM-friendly wrapper used by the FastAPI service.

    Writes each render to its own unique file under ``versions/`` so a video
    the browser is currently streaming never gets renamed or overwritten
    (avoids Windows WinError 32 file locks).
    """
    if not project.audio_path:
        raise ValueError("Audio file is required")

    audio_path = _resolve_path(project.audio_path)
    if not audio_path.exists():
        raise ValueError(f"Audio file not found: {audio_path}")

    narration = AudioFileClip(str(audio_path))
    voice_duration = float(narration.duration)
    narration.close()

    mappings = _image_mappings_from_scenes(project, scenes, voice_duration)
    out_dir = settings.project_output_dir(project.id)
    render_output = _next_render_output(project, out_dir)

    result = generate_documentary(
        project_id=str(project.id),
        image_mappings=mappings,
        voice_audio_path=str(audio_path),
        whisper_timestamps=project.whisper_timestamps or {},
        is_test_mode=bool(project.is_test_mode),
        on_progress=on_progress,
        output_path=render_output,
    )
    return Path(result)
