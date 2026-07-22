from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from history_channel.database import get_db
from history_channel.schemas import (
    FeedbackCreate,
    PipelineMessage,
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    ScriptGenerationResult,
    ScriptUpdate,
    SelectImageRequest,
    UserFeedbackOut,
    project_to_detail,
)
from history_channel.services import project_service

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _get_project_or_404(db: Session, project_id: int):
    project = project_service.get_project_detail(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=ProjectSummary, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    return project_service.create_project(db, payload.topic, payload.is_test_mode)


@router.get("", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)):
    return project_service.list_projects(db)


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, db: Session = Depends(get_db)):
    return project_to_detail(_get_project_or_404(db, project_id))


@router.post("/{project_id}/generate-script", response_model=ScriptGenerationResult)
def generate_script(project_id: int, db: Session = Depends(get_db)):
    project = _get_project_or_404(db, project_id)
    try:
        script, iterations, notes = project_service.run_script_generation(db, project)
        return ScriptGenerationResult(
            script_text=script,
            iterations=iterations,
            editor_notes=notes,
            had_warnings=bool(notes),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Script generation failed: {e}")


@router.put("/{project_id}/script", response_model=ProjectDetail)
def update_script(
    project_id: int, payload: ScriptUpdate, db: Session = Depends(get_db)
):
    project = _get_project_or_404(db, project_id)
    updated = project_service.approve_script(db, project, payload.script_text)
    return project_to_detail(updated)


@router.post("/{project_id}/feedback", response_model=UserFeedbackOut, status_code=201)
def submit_feedback(
    project_id: int, payload: FeedbackCreate, db: Session = Depends(get_db)
):
    project = _get_project_or_404(db, project_id)
    return project_service.add_feedback(
        db, project, payload.stage, payload.feedback_text
    )


@router.get("/{project_id}/feedback", response_model=list[UserFeedbackOut])
def get_feedback(project_id: int, db: Session = Depends(get_db)):
    _get_project_or_404(db, project_id)
    return project_service.list_feedback(db, project_id)


@router.post("/{project_id}/generate-audio", response_model=PipelineMessage)
def generate_audio_endpoint(project_id: int, db: Session = Depends(get_db)):
    project = _get_project_or_404(db, project_id)
    try:
        updated, reused, generated = project_service.run_audio_generation(db, project)
        msg = "Audio and timestamps generated successfully"
        if reused or generated:
            msg = (
                f"Audio ready — reused {reused} paragraph(s), "
                f"generated {generated} new paragraph(s) via ElevenLabs"
            )
        return PipelineMessage(
            message=msg,
            status=updated.status,
            paragraphs_reused=reused,
            paragraphs_generated=generated,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio generation failed: {e}")


@router.post("/{project_id}/generate-images", response_model=PipelineMessage)
def generate_images_endpoint(project_id: int, db: Session = Depends(get_db)):
    project = _get_project_or_404(db, project_id)
    try:
        updated = project_service.run_image_generation(db, project)
        return PipelineMessage(
            message="Images generated successfully",
            status=updated.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")


@router.patch("/{project_id}/scenes/{scene_id}/select-image", response_model=ProjectDetail)
def select_image(
    project_id: int,
    scene_id: int,
    payload: SelectImageRequest,
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(db, project_id)
    try:
        project_service.select_scene_image(db, project, scene_id, payload.image_id)
        return project_to_detail(_get_project_or_404(db, project_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/generate-video", response_model=PipelineMessage)
def generate_video_endpoint(project_id: int, db: Session = Depends(get_db)):
    """Asset-based gate: audio + images on disk, audio not stale. Status enum ignored."""
    project = _get_project_or_404(db, project_id)
    try:
        updated = project_service.run_video_generation(db, project)
        return PipelineMessage(
            message="Video generated successfully",
            status=updated.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video generation failed: {e}")
