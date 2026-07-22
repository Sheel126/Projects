from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from history_channel.config import settings
from history_channel.models import Base

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_SQLITE_COLUMNS = {
    "render_status": "VARCHAR(500)",
    "script_hash": "VARCHAR(64)",
    "audio_script_hash": "VARCHAR(64)",
    "images_script_hash": "VARCHAR(64)",
    "video_versions": "JSON",
}


def _ensure_sqlite_columns() -> None:
    """Add columns introduced after initial create_all (SQLite has no ALTER via ORM)."""
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "project_topics" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("project_topics")}
    with engine.begin() as conn:
        for name, col_type in _SQLITE_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE project_topics ADD COLUMN {name} {col_type}"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
