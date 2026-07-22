# History Channel Generator

Autonomous faceless historical documentary YouTube video pipeline. Enter a topic, generate a cinematic script with AI agents, produce narration and timestamps, generate scene images, and render a final MP4 — all from a single web dashboard.

## Prerequisites

- **Python 3.12+**
- **Node.js 20+**
- **FFmpeg** — required by MoviePy for video encoding ([download](https://ffmpeg.org/download.html))
- API keys for OpenAI, ElevenLabs, and Replicate (see setup below)

## Quick Start

### 1. Environment setup

```bash
cd history-channel-generator
cp .env.example .env
```

Edit `.env` and fill in your API keys:

| Variable | Where to get it |
|----------|-----------------|
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `ELEVENLABS_API_KEY` | [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys) |
| `ELEVENLABS_VOICE_ID` | ElevenLabs → Voices → select voice → copy Voice ID |
| `REPLICATE_API_TOKEN` | [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens) |

### 2. Background music (optional)

Cinematic assets live under `backend/assets/` (snake_case filenames):

```
backend/assets/overlays/film_grain_loop.mp4
backend/assets/overlays/dust_particles.mp4
backend/assets/audio/sfx/fast_whoosh.wav
backend/assets/audio/sfx/cinematic_boom.wav
backend/assets/audio/music/suspense_background.mp3
```

Or override music with `BACKGROUND_MUSIC_PATH` in `.env`. The bed is mixed at **-22 dB** under narration.

### 3. Start the backend

**Windows (easiest):**
```bash
cd backend
run.bat
```

**Manual:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Mac/Linux: source venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

> **Tip:** Stop the server (Ctrl+C) before running `pip install`. On Windows, use `python -m uvicorn` instead of `uvicorn` directly to avoid file-lock errors.

The API runs at `http://localhost:8000`. Health check: `GET /health`.

### 4. Start the frontend

```bash
cd frontend
npm install
ng serve --proxy-config proxy.conf.json
```

Open `http://localhost:4200`.

## Workflow

1. **Create a project** — Enter a historical topic. Toggle **Test Mode** for a fast preview (300 words, **3 images**, 720p).
2. **Phase 1: Script** — Click *Generate Script*. Submit agent feedback and regenerate to refine. Approve & Save.
3. **Phase 2: Audio** — ElevenLabs TTS + OpenAI Whisper timestamps.
4. **Phase 3: Images** — Flux Schnell generates **1 image per scene** (thumbnail = scene 1). No V1–V4 variations.
5. **Phase 4: Video** — Smooth Ken Burns + end hold. **Regenerate Video** works whenever audio + images exist on disk (status enum is not the gate). After render, use **Download for YouTube** (faststart MP4).

### Script changes
- Saving a new script keeps existing audio/images.
- **Audio stale (required):** regenerate audio before video. Small edits reuse unchanged paragraphs (fewer ElevenLabs calls).
- **Images stale (recommended):** regenerate images so visuals match the new wording.

## Image cost model

Uses **`black-forest-labs/flux-schnell`** (Apache 2.0 — personal and **commercial / YouTube** use allowed).

| Mode | Scenes | Images | Est. Replicate cost |
|------|--------|--------|---------------------|
| Test | 3 | 3 | ~\$0.01 |
| Production | 12 | 12 | ~\$0.04 |

## Test Mode vs Production

| Setting | Production | Test Mode |
|---------|------------|-----------|
| Script length | ~1,500 words | ~300 words |
| Scene images | 12 (1 each) | 3 (1 each) |
| Video resolution | 1920×1080 | 1280×720 |
| End pad after narration | 1.5s | 1.5s |

## Output Files

```
backend/output/{project_id}/
├── narration.mp3
├── images/
│   ├── scene_0.png
│   ├── scene_1.png
│   └── …
└── final.mp4
```

Served at `/media/{project_id}/...` for UI preview.

## Troubleshooting

- **FFmpeg not found** — Ensure `ffmpeg` is on your PATH.
- **CORS errors** — Use `ng serve --proxy-config proxy.conf.json`.
- **Replicate 429 / throttled** — Free tier is ~6 predictions/min. The app spaces calls and retries. Add billing for higher throughput: [replicate.com/account/billing](https://replicate.com/account/billing).
- **Regenerate Video** — Available once images exist (`images_ready` or `video_ready`). Status panel shows Ken Burns / mix / encode progress.
