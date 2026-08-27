from pathlib import Path

from sqlalchemy import text

from app.db.base import Base
from app.db.init_db import init_db
from app.db.session import (
    create_engine_for_path,
    create_session_factory,
    get_database_path,
)


def test_default_database_path_uses_app_data_dir(monkeypatch, tmp_path) -> None:
    app_data_dir = tmp_path / "data"
    monkeypatch.setenv("APP_DATA_DIR", str(app_data_dir))

    assert get_database_path() == app_data_dir / "ai_director.db"


def test_engine_initialization_creates_database_file(tmp_path) -> None:
    database_path = tmp_path / "nested" / "ai_director.db"
    database_engine = create_engine_for_path(database_path)

    assert not database_path.exists()

    init_db(database_engine)

    assert database_path.exists()
    assert database_engine.url.database == database_path.resolve().as_posix()
    assert set(Base.metadata.tables) == {
        "assets",
        "generation_jobs",
        "projects",
        "scenes",
        "workflow_templates",
    }
    database_engine.dispose()


def test_session_executes_select_and_closes(tmp_path) -> None:
    database_path = Path(tmp_path) / "ai_director.db"
    database_engine = create_engine_for_path(database_path)
    init_db(database_engine)
    session_factory = create_session_factory(database_engine)
    session = session_factory()

    try:
        assert session.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        session.close()

    assert not session.in_transaction()
    session.close()
    database_engine.dispose()
