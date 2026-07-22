from datetime import datetime

from pydantic import BaseModel, Field

from history_channel.models import ProjectStatus, ProjectTopic
from history_channel import readiness


class ProjectCreate(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    is_test_mode: bool = False


class ProjectSummary(BaseModel):
    id: int
    topic: str
    is_test_mode: bool
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GeneratedImageOut(BaseModel):
    id: int
    scene_id: int | None
    variation_index: int
    file_path: str
    is_thumbnail: bool

    model_config = {"from_attributes": True}


class SceneOut(BaseModel):
    id: int
    scene_order: int
    narrative_excerpt: str
    image_prompt: str | None
    start_time: float | None
    end_time: float | None
    selected_image_id: int | None
    images: list[GeneratedImageOut] = []

    model_config = {"from_attributes": True}


class UserFeedbackOut(BaseModel):
    id: int
    project_id: int
    stage: str
    feedback_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectDetail(BaseModel):
    id: int
    topic: str
    is_test_mode: bool
    status: ProjectStatus
    script_text: str | None
    audio_path: str | None
    whisper_timestamps: dict | None
    thumbnail_path: str | None
    video_path: str | None
    video_versions: list[dict] | None = None
    render_status: str | None = None
    script_hash: str | None = None
    audio_script_hash: str | None = None
    images_script_hash: str | None = None
    created_at: datetime
    updated_at: datetime
    scenes: list[SceneOut] = []
    feedback: list[UserFeedbackOut] = []
    can_generate_audio: bool = False
    can_generate_images: bool = False
    can_generate_video: bool = False
    audio_stale: bool = False
    images_stale: bool = False
    pipeline_warnings: list[str] = []

    model_config = {"from_attributes": True}


def project_to_detail(project: ProjectTopic) -> ProjectDetail:
    """Build API detail with asset-based readiness flags."""
    # Backfill legacy renders on first read so the UI history is complete
    from history_channel.video_editor import backfill_video_versions

    if backfill_video_versions(project):
        try:
            from sqlalchemy.orm.attributes import flag_modified
            from sqlalchemy.orm import object_session

            flag_modified(project, "video_versions")
            sess = object_session(project)
            if sess is not None:
                sess.commit()
        except Exception:
            pass

    base = ProjectDetail.model_validate(project)
    return base.model_copy(
        update={
            "can_generate_audio": readiness.can_generate_audio(project),
            "can_generate_images": readiness.can_generate_images(project),
            "can_generate_video": readiness.can_generate_video(project),
            "audio_stale": readiness.audio_stale(project),
            "images_stale": readiness.images_stale(project),
            "pipeline_warnings": readiness.pipeline_warnings(project),
        }
    )


class ScriptUpdate(BaseModel):
    script_text: str = Field(min_length=50)


class FeedbackCreate(BaseModel):
    stage: str = Field(min_length=1, max_length=100)
    feedback_text: str = Field(min_length=1)


class ScriptGenerationResult(BaseModel):
    script_text: str
    iterations: int
    editor_notes: list[str]
    had_warnings: bool = False


class SelectImageRequest(BaseModel):
    image_id: int


class PipelineMessage(BaseModel):
    message: str
    status: ProjectStatus
    paragraphs_reused: int | None = None
    paragraphs_generated: int | None = None
