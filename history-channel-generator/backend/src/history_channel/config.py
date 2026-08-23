from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_PROJECT_ROOT = _BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            _PROJECT_ROOT / ".env",
            _BACKEND_ROOT / ".env",
            ".env",
            "../.env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    replicate_api_token: str = ""
    database_url: str = "sqlite:///./history_app.db"
    port: int = 8000
    background_music_path: str = "./assets/audio/music/suspense_background.mp3"

    # Image generation provider: comfyui (default, local) or replicate
    image_provider: str = "comfyui"

    # ComfyUI — local FLUX / workflow-driven image generation
    comfyui_base_url: str = "http://127.0.0.1:8188"
    comfyui_workflow_path: str = ""
    comfyui_timeout_seconds: float = 300.0
    comfyui_poll_interval_seconds: float = 1.5
    comfyui_default_width: int = 1280
    comfyui_default_height: int = 720
    comfyui_output_subdir: str = ""

    # Flux Schnell — used only when IMAGE_PROVIDER=replicate
    flux_model: str = "black-forest-labs/flux-schnell"

    # Production defaults
    script_word_count_prod: int = 1500
    script_word_count_test: int = 300
    scene_count_prod_min: int = 12
    scene_count_prod_max: int = 12
    scene_count_test_min: int = 3
    scene_count_test_max: int = 3
    video_width_prod: int = 1920
    video_height_prod: int = 1080
    video_width_test: int = 1280
    video_height_test: int = 720
    max_editor_retries: int = 3
    image_generation_timeout_sec: float = 900.0
    image_download_timeout_sec: float = 300.0
    image_download_retries: int = 5

    # Video polish
    video_end_padding_sec: float = 1.5
    kb_zoom_end: float = 1.06
    kb_pan_fraction: float = 0.04
    kb_crossfade_sec: float = 0.4

    flux_negative_prompt: str = (
        "text, typography, writing, letters, watermarks, signatures, "
        "words, signs, gibberish"
    )

    @property
    def backend_root(self) -> Path:
        return _BACKEND_ROOT

    @property
    def output_dir(self) -> Path:
        path = self.backend_root / "output"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def project_output_dir(self, project_id: int) -> Path:
        path = self.output_dir / str(project_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def script_word_count(self, is_test_mode: bool) -> int:
        return self.script_word_count_test if is_test_mode else self.script_word_count_prod

    def scene_count_range(self, is_test_mode: bool) -> tuple[int, int]:
        if is_test_mode:
            return self.scene_count_test_min, self.scene_count_test_max
        return self.scene_count_prod_min, self.scene_count_prod_max

    def video_resolution(self, is_test_mode: bool) -> tuple[int, int]:
        if is_test_mode:
            return self.video_width_test, self.video_height_test
        return self.video_width_prod, self.video_height_prod

    def comfyui_workflow_path_resolved(self) -> Path:
        if self.comfyui_workflow_path.strip():
            path = Path(self.comfyui_workflow_path)
            if not path.is_absolute():
                path = self.backend_root / path
            return path
        return self.backend_root / "assets" / "comfyui" / "flux_schnell_16x9.json"

    def test_images_output_dir(self) -> Path:
        path = self.output_dir / "test_images"
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
