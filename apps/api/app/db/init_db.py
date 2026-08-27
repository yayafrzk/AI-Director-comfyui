from pathlib import Path

from sqlalchemy.engine import Engine

from app.db.base import Base
from app.db.session import engine
from app.models.asset import Asset  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.scene import Scene  # noqa: F401
from app.models.workflow_template import WorkflowTemplate  # noqa: F401


def _ensure_database_parent(database_engine: Engine) -> None:
    database = database_engine.url.database
    if database and database != ":memory:":
        Path(database).expanduser().resolve().parent.mkdir(
            parents=True,
            exist_ok=True,
        )


def init_db(database_engine: Engine | None = None) -> None:
    target_engine = database_engine or engine
    _ensure_database_parent(target_engine)
    Base.metadata.create_all(bind=target_engine)
