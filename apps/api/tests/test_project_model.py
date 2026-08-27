from datetime import datetime, timezone
from time import sleep
from uuid import UUID

from sqlalchemy import inspect, select

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate


def _assert_utc(value: datetime) -> None:
    assert value.tzinfo is not None
    assert value.utcoffset() is not None
    assert value.utcoffset().total_seconds() == 0


def test_project_table_and_model_round_trip(tmp_path) -> None:
    database_path = tmp_path / "project.db"
    database_engine = create_engine_for_path(database_path)

    try:
        init_db(database_engine)
        assert set(inspect(database_engine).get_table_names()) == {
            "assets",
            "generation_jobs",
            "projects",
            "scenes",
            "workflow_templates",
        }

        session_factory = create_session_factory(database_engine)
        project = Project(
            name="测试项目",
            description="用于 ORM 测试",
            aspect_ratio="16:9",
            width=1920,
            height=1080,
            fps=24,
        )

        with session_factory() as session:
            session.add(project)
            session.commit()
            session.refresh(project)

            assert isinstance(project.id, str)
            UUID(project.id)
            assert project.name == "测试项目"
            assert project.description == "用于 ORM 测试"
            assert project.aspect_ratio == "16:9"
            assert project.width == 1920
            assert project.height == 1080
            assert project.fps == 24
            _assert_utc(project.created_at)
            _assert_utc(project.updated_at)

            loaded_project = session.scalar(
                select(Project).where(Project.id == project.id)
            )

            assert loaded_project is not None
            assert loaded_project.id == project.id
            assert loaded_project.name == project.name
            assert loaded_project.created_at == project.created_at
            assert loaded_project.updated_at == project.updated_at
            _assert_utc(loaded_project.created_at)
            _assert_utc(loaded_project.updated_at)
    finally:
        database_engine.dispose()


def test_project_updated_at_updates_on_change(tmp_path) -> None:
    database_engine = create_engine_for_path(tmp_path / "project.db")

    try:
        init_db(database_engine)
        session_factory = create_session_factory(database_engine)

        with session_factory() as session:
            project = Project(
                name="Initial",
                description=None,
                aspect_ratio="9:16",
                width=1080,
                height=1920,
                fps=30,
            )
            session.add(project)
            session.commit()
            session.refresh(project)
            previous_updated_at = project.updated_at

            sleep(0.001)
            project.name = "Updated"
            session.commit()
            session.refresh(project)

            assert project.updated_at > previous_updated_at
            _assert_utc(project.updated_at)
    finally:
        database_engine.dispose()


def test_project_schemas_validate_partial_updates_and_orm_reads(tmp_path) -> None:
    create = ProjectCreate(
        name="Schema project",
        description="Schema description",
        aspect_ratio="16:9",
        width=1920,
        height=1080,
        fps=24,
    )
    assert create.name == "Schema project"

    update = ProjectUpdate(name="Renamed")
    assert update.model_dump(exclude_unset=True) == {"name": "Renamed"}

    database_engine = create_engine_for_path(tmp_path / "project.db")
    try:
        init_db(database_engine)
        session_factory = create_session_factory(database_engine)

        with session_factory() as session:
            project = Project(**create.model_dump())
            session.add(project)
            session.commit()
            session.refresh(project)

            read = ProjectRead.model_validate(project)

            assert read.id == project.id
            assert read.name == project.name
            assert read.description == project.description
            assert read.created_at == project.created_at
            assert read.updated_at == project.updated_at
    finally:
        database_engine.dispose()
