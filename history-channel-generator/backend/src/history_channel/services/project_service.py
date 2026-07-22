from sqlalchemy.orm import Session, joinedload

from history_channel.agents.script_pipeline import generate_script_with_reflection
from history_channel.models import (
    GeneratedImage,
    ProjectStatus,
    ProjectTopic,
    Scene,
    UserFeedback,
)
from history_channel.readiness import (
    can_generate_audio,
    can_generate_images,
    can_generate_video,
    hash_script,
    has_audio,
    sync_status_from_assets,
)
from history_channel.services.audio_service import generate_audio
from history_channel.services.image_service import generate_images


def get_project_detail(db: Session, project_id: int) -> ProjectTopic | None:
    project = (
        db.query(ProjectTopic)
        .options(
            joinedload(ProjectTopic.feedback),
            joinedload(ProjectTopic.scenes).joinedload(Scene.images),
            joinedload(ProjectTopic.images),
        )
        .filter(ProjectTopic.id == project_id)
        .first()
    )
    if project and project.script_text and not project.script_hash:
        project.script_hash = hash_script(project.script_text)
        # Backfill hashes for legacy projects so regenerate works without re-running phases
        if has_audio(project) and not project.audio_script_hash:
            project.audio_script_hash = project.script_hash
        if project.scenes and not project.images_script_hash:
            # If images exist on disk via readiness, align hash
            from history_channel.readiness import has_images

            if has_images(project):
                project.images_script_hash = project.script_hash
        sync_status_from_assets(project)
        db.commit()
        db.refresh(project)
    return project


def create_project(db: Session, topic: str, is_test_mode: bool) -> ProjectTopic:
    project = ProjectTopic(topic=topic, is_test_mode=is_test_mode)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_projects(db: Session) -> list[ProjectTopic]:
    return db.query(ProjectTopic).order_by(ProjectTopic.created_at.desc()).all()


def run_script_generation(db: Session, project: ProjectTopic) -> tuple[str, int, list[str]]:
    script, iterations, notes = generate_script_with_reflection(
        db, project.id, project.topic, project.is_test_mode
    )
    project.script_text = script
    project.script_hash = hash_script(script)
    project.status = ProjectStatus.SCRIPT_READY
    db.commit()
    db.refresh(project)
    return script, iterations, notes


def approve_script(db: Session, project: ProjectTopic, script_text: str) -> ProjectTopic:
    project.script_text = script_text
    project.script_hash = hash_script(script_text)
    # Keep audio/images; staleness flags come from hash mismatch
    if not project.audio_path:
        project.status = ProjectStatus.SCRIPT_READY
    else:
        sync_status_from_assets(project)
        # If audio is now stale, don't claim video_ready
        from history_channel.readiness import audio_stale

        if audio_stale(project) and project.status == ProjectStatus.VIDEO_READY:
            project.status = ProjectStatus.IMAGES_READY
    db.commit()
    db.refresh(project)
    return project


def add_feedback(
    db: Session, project: ProjectTopic, stage: str, feedback_text: str
) -> UserFeedback:
    row = UserFeedback(
        project_id=project.id,
        stage=stage,
        feedback_text=feedback_text,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_feedback(db: Session, project_id: int) -> list[UserFeedback]:
    return (
        db.query(UserFeedback)
        .filter(UserFeedback.project_id == project_id)
        .order_by(UserFeedback.created_at.asc())
        .all()
    )


def select_scene_image(
    db: Session, project: ProjectTopic, scene_id: int, image_id: int
) -> Scene:
    scene = (
        db.query(Scene)
        .filter(Scene.id == scene_id, Scene.project_id == project.id)
        .first()
    )
    if not scene:
        raise ValueError("Scene not found")

    image = (
        db.query(GeneratedImage)
        .filter(
            GeneratedImage.id == image_id,
            GeneratedImage.project_id == project.id,
            GeneratedImage.scene_id == scene_id,
        )
        .first()
    )
    if not image:
        raise ValueError("Image not found for this scene")

    scene.selected_image_id = image_id
    db.commit()
    db.refresh(scene)
    return scene


def run_audio_generation(
    db: Session, project: ProjectTopic
) -> tuple[ProjectTopic, int, int]:
    if not can_generate_audio(project):
        raise ValueError("Script must be approved before generating audio")
    return generate_audio(db, project)


def run_image_generation(db: Session, project: ProjectTopic) -> ProjectTopic:
    if not can_generate_images(project):
        raise ValueError(
            "Audio files must exist before generating images "
            "(generate audio first, or wait for existing audio on disk)"
        )
    return generate_images(db, project)


def _set_render_status(db: Session, project: ProjectTopic, message: str) -> None:
    project.render_status = message
    db.commit()


def run_video_generation(db: Session, project: ProjectTopic) -> ProjectTopic:
    from history_channel.readiness import audio_stale, file_exists, has_audio, has_images

    # Auto-heal selected_image_id if missing but files exist
    scenes = (
        db.query(Scene)
        .options(joinedload(Scene.images))
        .filter(Scene.project_id == project.id)
        .order_by(Scene.scene_order.asc())
        .all()
    )
    for scene in scenes:
        if scene.selected_image_id:
            continue
        first = next(iter(scene.images or []), None)
        if first and file_exists(first.file_path):
            scene.selected_image_id = first.id
    db.commit()

    # Re-load with relationships for readiness + render
    project = get_project_detail(db, project.id) or project

    if not can_generate_video(project):
        if not has_audio(project):
            raise ValueError("Audio is missing — generate audio before video")
        if audio_stale(project):
            raise ValueError(
                "Script changed since audio — regenerate audio before video"
            )
        if not has_images(project):
            raise ValueError("Images are missing — generate images before video")
        raise ValueError("Cannot render video — missing required assets")

    scenes = (
        db.query(Scene)
        .options(joinedload(Scene.images))
        .filter(Scene.project_id == project.id)
        .order_by(Scene.scene_order.asc())
        .all()
    )
    if not scenes:
        raise ValueError("No scenes found")

    for scene in scenes:
        if not scene.selected_image_id:
            first = next(iter(scene.images or []), None)
            if first:
                scene.selected_image_id = first.id
            else:
                raise ValueError(f"Scene {scene.scene_order + 1} has no selected image")
    db.commit()

    def on_progress(message: str) -> None:
        _set_render_status(db, project, message)

    try:
        on_progress("Starting cinematic render…")
        from history_channel.video_editor import (
            append_video_version,
            backfill_video_versions,
            render_video,
        )
        from sqlalchemy.orm.attributes import flag_modified

        # Preserve any legacy final.mp4 as Render 1 in the history *before*
        # we pick the next version number — otherwise the fresh render would
        # collide with N=1 and lose the previous rendition from the UI.
        if backfill_video_versions(project):
            flag_modified(project, "video_versions")
            db.commit()

        # Each render writes to a unique versions/render_<N>_<stamp>.mp4 file,
        # so the currently-playing video in the browser is never touched.
        video_path = render_video(project, scenes, on_progress=on_progress)

        # Persist this render as a new history row + point video_path at it.
        versions = append_video_version(project.video_versions, video_path)
        project.video_versions = versions
        flag_modified(project, "video_versions")
        project.video_path = str(video_path)
        project.status = ProjectStatus.VIDEO_READY
        project.render_status = "Complete"
        db.commit()
        db.refresh(project)
        return project
    except Exception as exc:
        project.render_status = f"Failed: {exc}"
        db.commit()
        raise
