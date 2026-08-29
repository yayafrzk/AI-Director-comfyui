from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import inspect, select, update
from sqlalchemy.exc import IntegrityError

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory
from app.models.project import Project
from app.models.scene import Scene
from app.schemas.scene import SceneCreate, SceneRead, SceneUpdate


def _assert_utc(value: datetime) -> None:
    assert value.tzinfo is not None
    assert value.utcoffset() is not None
    assert value.utcoffset().total_seconds() == 0


def _project(name: str) -> Project:
    return Project(
        name=name,
        description=None,
        aspect_ratio="9:16",
        width=1080,
        height=1920,
        fps=30,
    )


def _scene(project_id: str, scene_number: int, **overrides) -> Scene:
    values = {
        "project_id": project_id,
        "scene_number": scene_number,
        "title": "测试分镜",
        "description": "分镜描述",
        "prompt": "cinematic close-up",
        "negative_prompt": "blurry",
        "seed": 1 << 50,
        "duration_seconds": 5.5,
        "workflow_template_id": "workflow-template-id",
        "selected_asset_id": "asset-id",
        "status": "draft",
    }
    values.update(overrides)
    return Scene(**values)


def test_scene_table_and_model_round_trip(tmp_path) -> None:
    database_engine = create_engine_for_path(tmp_path / "scene.db")

    try:
        init_db(database_engine)
        assert set(inspect(database_engine).get_table_names()) == {
            "assets",
            "generation_jobs",
            "generation_outputs",
            "projects",
            "scenes",
            "workflow_templates",
        }

        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            project = _project("Scene project")
            session.add(project)
            session.commit()

            scene = _scene(project.id, scene_number=1)
            session.add(scene)
            session.commit()
            session.refresh(scene)

            assert isinstance(scene.id, str)
            UUID(scene.id)
            assert scene.project_id == project.id
            assert scene.scene_number == 1
            assert scene.title == "测试分镜"
            assert scene.description == "分镜描述"
            assert scene.prompt == "cinematic close-up"
            assert scene.negative_prompt == "blurry"
            assert scene.seed == 1 << 50
            assert scene.duration_seconds == 5.5
            assert scene.workflow_template_id == "workflow-template-id"
            assert scene.selected_asset_id == "asset-id"
            assert scene.status == "draft"
            _assert_utc(scene.created_at)
            _assert_utc(scene.updated_at)

            session.execute(
                update(Scene)
                .where(Scene.id == scene.id)
                .values(updated_at=datetime(2000, 1, 1, tzinfo=timezone.utc))
            )
            session.commit()
            session.expire(scene)
            scene.title = "更新后的分镜"
            session.commit()
            session.refresh(scene)
            assert scene.updated_at > datetime(2000, 1, 1, tzinfo=timezone.utc)

            loaded_scene = session.scalar(select(Scene).where(Scene.id == scene.id))
            assert loaded_scene is not None
            assert loaded_scene.title == "更新后的分镜"
    finally:
        database_engine.dispose()


def test_scene_constraints_and_nullable_fields(tmp_path) -> None:
    database_engine = create_engine_for_path(tmp_path / "scene.db")

    try:
        init_db(database_engine)
        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            first_project = _project("First")
            second_project = _project("Second")
            session.add_all([first_project, second_project])
            session.commit()

            session.add(
                _scene(
                    first_project.id,
                    scene_number=1,
                    seed=None,
                    workflow_template_id=None,
                    selected_asset_id=None,
                )
            )
            session.add(_scene(second_project.id, scene_number=1))
            session.commit()

            nullable_scene = session.scalar(select(Scene).where(Scene.project_id == first_project.id))
            assert nullable_scene is not None
            assert nullable_scene.seed is None
            assert nullable_scene.workflow_template_id is None
            assert nullable_scene.selected_asset_id is None

            session.add(_scene(first_project.id, scene_number=1))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

            session.add(_scene("missing-project", scene_number=2))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        database_engine.dispose()


def test_scene_schemas_validate_partial_updates_and_orm_reads(tmp_path) -> None:
    create = SceneCreate(
        title="Schema scene",
        description="Schema description",
        prompt="Schema prompt",
        negative_prompt=None,
        seed=None,
        duration_seconds=8.0,
        workflow_template_id=None,
    )
    assert create.title == "Schema scene"

    update_schema = SceneUpdate(title="新的标题")
    assert update_schema.model_dump(exclude_unset=True) == {"title": "新的标题"}

    database_engine = create_engine_for_path(tmp_path / "scene.db")
    try:
        init_db(database_engine)
        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            project = _project("Schema project")
            session.add(project)
            session.commit()

            scene = _scene(project.id, scene_number=1, **create.model_dump())
            session.add(scene)
            session.commit()
            session.refresh(scene)

            read = SceneRead.model_validate(scene)
            assert read.id == scene.id
            assert read.project_id == project.id
            assert read.scene_number == 1
            assert read.title == "Schema scene"
            assert read.created_at == scene.created_at
            assert read.updated_at == scene.updated_at
    finally:
        database_engine.dispose()
