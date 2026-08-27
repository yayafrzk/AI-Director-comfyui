from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def get_database_path() -> Path:
    return get_settings().app_data_dir / "ai_director.db"


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite:///{database_path.as_posix()}"


def create_engine_for_path(database_path: Path | str | None = None) -> Engine:
    path = Path(database_path or get_database_path()).expanduser().resolve()
    database_engine = create_engine(
        _sqlite_url(path),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(database_engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return database_engine


engine = create_engine_for_path()
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def create_session_factory(database_engine: Engine | None = None):
    return sessionmaker(
        bind=database_engine or engine,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )


def get_db():
    """Provide one database session for the duration of a request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
