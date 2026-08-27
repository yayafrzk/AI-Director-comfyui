from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect, select

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory
from app.models.asset import Asset
from app.models.project import Project
from app.models.scene import Scene
from app.schemas.asset import AssetCreate, AssetRead


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


def _scene(project_id: str) -> Scene:
    return Scene(
        project_id=project_id,
        scene_number=1,
        title="Asset scene",
        description=None,
        prompt=None,
        negative_prompt=None,
        seed=None,
        duration_seconds=2.0,
        workflow_template_id=None,
        selected_asset_id=None,
        status="draft",
    )


def _asset(project_id: str, scene_id: str | None, **overrides) -> Asset:
    values = {
        "project_id": project_id,
        "scene_id": scene_id,
        "type": "image",
        "role": "first_frame",
        "relative_path": "images/frame_001.png",
        "thumbnail_path": "thumbnails/frame_001.jpg",
        "mime_type": "image/png",
        "width": 1080,
        "height": 1920,
        "duration_seconds": None,
        "size_bytes": 1 << 40,
        "hash": "asset-hash",
    }
    values.update(overrides)
    return Asset(**values)


def test_asset_table_orm_round_trip_and_schema_serialization(tmp_path) -> None:
    database_engine = create_engine_for_path(tmp_path / "asset.db")

    try:
        init_db(database_engine)
        assert set(inspect(database_engine).get_table_names()) == {"assets", "projects", "scenes"}

        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            project = _project("Asset project")
            session.add(project)
            session.commit()

            scene = _scene(project.id)
            session.add(scene)
            session.commit()

            asset = _asset(project.id, scene.id)
            session.add(asset)
            session.commit()
            session.refresh(asset)

            assert isinstance(asset.id, str)
            UUID(asset.id)
            assert asset.project_id == project.id
            assert asset.scene_id == scene.id
            assert asset.type == "image"
            assert asset.role == "first_frame"
            assert asset.relative_path == "images/frame_001.png"
            assert asset.thumbnail_path == "thumbnails/frame_001.jpg"
            assert asset.mime_type == "image/png"
            assert asset.width == 1080
            assert asset.height == 1920
            assert asset.duration_seconds is None
            assert asset.size_bytes == 1 << 40
            assert asset.hash == "asset-hash"
            _assert_utc(asset.created_at)

            loaded_asset = session.scalar(select(Asset).where(Asset.id == asset.id))
            assert loaded_asset is not None
            assert loaded_asset.relative_path == asset.relative_path

            read = AssetRead.model_validate(asset)
            assert read.id == asset.id
            assert read.project_id == project.id
            assert read.scene_id == scene.id
            assert read.created_at == asset.created_at
    finally:
        database_engine.dispose()


def test_project_level_asset_accepts_nullable_metadata(tmp_path) -> None:
    database_engine = create_engine_for_path(tmp_path / "asset.db")

    try:
        init_db(database_engine)
        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            project = _project("Project-level asset")
            session.add(project)
            session.commit()

            asset = _asset(
                project.id,
                scene_id=None,
                thumbnail_path=None,
                width=None,
                height=None,
                duration_seconds=None,
                hash=None,
            )
            session.add(asset)
            session.commit()
            session.refresh(asset)

            assert asset.scene_id is None
            assert asset.thumbnail_path is None
            assert asset.width is None
            assert asset.height is None
            assert asset.duration_seconds is None
            assert asset.hash is None
    finally:
        database_engine.dispose()


@pytest.mark.parametrize("asset_type", ["image", "video", "audio", "reference"])
def test_asset_create_schema_accepts_supported_types(asset_type: str) -> None:
    asset = AssetCreate(
        project_id="project-id",
        scene_id=None,
        type=asset_type,
        role="reference",
        relative_path="images/reference.png",
        thumbnail_path=None,
        mime_type="image/png",
        width=None,
        height=None,
        duration_seconds=0,
        size_bytes=0,
        hash=None,
    )

    assert asset.type == asset_type
    assert asset.scene_id is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"type": "unknown"},
        {"relative_path": ""},
        {"mime_type": ""},
        {"size_bytes": -1},
        {"width": 0},
        {"height": -1},
        {"duration_seconds": -0.1},
    ],
)
def test_asset_create_schema_rejects_invalid_metadata(overrides: dict[str, object]) -> None:
    values = {
        "project_id": "project-id",
        "scene_id": None,
        "type": "video",
        "role": "output",
        "relative_path": "videos/output.mp4",
        "thumbnail_path": None,
        "mime_type": "video/mp4",
        "width": 1920,
        "height": 1080,
        "duration_seconds": 3.5,
        "size_bytes": 100,
        "hash": None,
    }
    values.update(overrides)

    with pytest.raises(ValidationError):
        AssetCreate(**values)
