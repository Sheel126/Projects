import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class ProjectStatus(str, enum.Enum):
    CREATED = "created"
    SCRIPT_READY = "script_ready"
    AUDIO_READY = "audio_ready"
    IMAGES_READY = "images_ready"
    VIDEO_READY = "video_ready"


class Base(DeclarativeBase):
    pass


class ProjectTopic(Base):
    __tablename__ = "project_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    is_test_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.CREATED, nullable=False
    )
    script_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    whisper_timestamps: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_versions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    render_status: Mapped[str | None] = mapped_column(String(500), nullable=True)
    script_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audio_script_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    images_script_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    feedback: Mapped[list["UserFeedback"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    scenes: Mapped[list["Scene"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Scene.scene_order"
    )
    images: Mapped[list["GeneratedImage"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project_topics.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    feedback_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["ProjectTopic"] = relationship(back_populates="feedback")


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project_topics.id"), nullable=False)
    scene_order: Mapped[int] = mapped_column(Integer, nullable=False)
    narrative_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    image_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    selected_image_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    project: Mapped["ProjectTopic"] = relationship(back_populates="scenes")
    images: Mapped[list["GeneratedImage"]] = relationship(
        back_populates="scene",
        foreign_keys="GeneratedImage.scene_id",
        cascade="all, delete-orphan",
    )


class GeneratedImage(Base):
    __tablename__ = "generated_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project_topics.id"), nullable=False)
    scene_id: Mapped[int | None] = mapped_column(ForeignKey("scenes.id"), nullable=True)
    variation_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    is_thumbnail: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Mapped["ProjectTopic"] = relationship(back_populates="images")
    scene: Mapped["Scene | None"] = relationship(
        back_populates="images", foreign_keys=[scene_id]
    )
