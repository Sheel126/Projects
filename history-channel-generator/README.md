# History Channel Generator

Autonomous faceless historical documentary YouTube video pipeline. Enter a topic, generate a cinematic script with AI agents, produce narration and timestamps, generate scene images locally, and render a final MP4 — all from a single web dashboard.

## Prerequisites

- **Python 3.12+**
- **Node.js 20+**
- **FFmpeg** — required by MoviePy for video encoding ([download](https://ffmpeg.org/download.html))
- **ComfyUI** — local image generation (default). Start ComfyUI separately before generating images.
- API keys for OpenAI and ElevenLabs (see setup below)
- Optional: Replicate token if you switch `IMAGE_PROVIDER=replicate`

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
| `REPLICATE_API_TOKEN` | Only if `IMAGE_PROVIDER=replicate` |

### 2. Local image generation (ComfyUI — default)

Image generation uses **ComfyUI over HTTP** with a workflow JSON file. The model (e.g. FLUX.1 Schnell FP8) is chosen inside your ComfyUI workflow, not hardcoded in this app.

1. Install and start [ComfyUI](https://github.com/comfyanonymous/ComfyUI) locally.
2. Ensure it is reachable at `http://127.0.0.1:8188` (or set `COMFYUI_BASE_URL`).
3. Install a FLUX Schnell workflow/models compatible with the bundled workflow, or export your own workflow and point `COMFYUI_WORKFLOW_PATH` at it.

Default workflow file:

```
backend/assets/comfyui/flux_schnell_16x9.json
```

Expected node mapping (update `providers/comfyui_workflow.py` if your export uses different IDs):

| Parameter | Node | Field |
|-----------|------|-------|
| Prompt | `6` | `text` |
| Width / Height | `27` | `width`, `height` |
| Seed | `25` | `noise_seed` |

Environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `IMAGE_PROVIDER` | `comfyui` | `comfyui` or `replicate` |
| `COMFYUI_BASE_URL` | `http://127.0.0.1:8188` | ComfyUI HTTP API |
| `COMFYUI_WORKFLOW_PATH` | bundled JSON | Workflow template path |
| `COMFYUI_TIMEOUT_SECONDS` | `300` | Max wait per image |
| `COMFYUI_POLL_INTERVAL_SECONDS` | `1.5` | Poll interval |
| `COMFYUI_DEFAULT_WIDTH` | `1280` | 16:9 default width |
| `COMFYUI_DEFAULT_HEIGHT` | `720` | 16:9 default height |

Local generation is slower than cloud APIs but avoids per-image API costs.

### 3. Background music (optional)

Cinematic assets live under `backend/assets/` (snake_case filenames):

```
backend/assets/overlays/film_grain_loop.mp4
backend/assets/overlays/dust_particles.mp4
backend/assets/audio/music/suspense_background.mp3
```

Or override music with `BACKGROUND_MUSIC_PATH` in `.env`.

### 4. Start the backend

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

The API runs at `http://localhost:8000`. Health check: `GET /health`.

### 5. Start the frontend

```bash
cd frontend
npm install
ng serve --proxy-config proxy.conf.json
```

Open `http://localhost:4200`.

## Image Test UI

Use **Image Test** (link on the dashboard, or `/image-test`) to preview prompts before running a full project batch:

1. Enter a prompt
2. Optionally set width, height, and seed
3. Click **Generate Test Image**
4. Preview the result and inspect generation time / saved path

Test images are saved under:

```
backend/output/test_images/
```

and served at `/media/test_images/...`.

The test endpoint uses the **same provider** as project scene generation (`POST /api/v1/images/test`).

## Workflow

1. **Create a project** — Enter a historical topic. Toggle **Test Mode** for a fast preview (300 words, **3 images**, 720p).
2. **Phase 1: Script** — Click *Generate Script*. Submit agent feedback and regenerate to refine. Approve & Save.
3. **Phase 2: Audio** — ElevenLabs TTS + OpenAI Whisper timestamps.
4. **Phase 3: Images** — Local ComfyUI generates **1 image per scene** (thumbnail = scene 1).
5. **Phase 4: Video** — Smooth Ken Burns + end hold. **Regenerate Video** works whenever audio + images exist on disk.

### Script changes
- Saving a new script keeps existing audio/images.
- **Audio stale (required):** regenerate audio before video.
- **Images stale (recommended):** regenerate images so visuals match the new wording.

## Image provider switching

Default:

```env
IMAGE_PROVIDER=comfyui
```

Optional Replicate fallback (no silent fallback — if ComfyUI is selected and unavailable, you get a clear error):

```env
IMAGE_PROVIDER=replicate
REPLICATE_API_TOKEN=your_token
```

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
└── versions/
    └── render_N_*.mp4

backend/output/test_images/
└── test_*.png
```

Served at `/media/{project_id}/...` and `/media/test_images/...` for UI preview.

## Troubleshooting

- **FFmpeg not found** — Ensure `ffmpeg` is on your PATH.
- **CORS errors** — Use `ng serve --proxy-config proxy.conf.json`.
- **ComfyUI unavailable** — Start ComfyUI and confirm `COMFYUI_BASE_URL`. Check workflow node IDs match your export.
- **Workflow rejected** — Export a compatible FLUX Schnell workflow from ComfyUI and update `COMFYUI_WORKFLOW_PATH` or edit the bundled JSON / mapping.
- **Replicate 429 / throttled** — Only applies when `IMAGE_PROVIDER=replicate`.

## Tests

Backend:

```bash
cd backend
PYTHONPATH=src python -m unittest discover -s tests -v
```

Frontend (optional):

```bash
cd frontend
npm test -- --watch=false --browsers=ChromeHeadless
```
