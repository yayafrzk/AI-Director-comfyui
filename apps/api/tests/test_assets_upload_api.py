import asyncio
from pathlib import Path

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory, get_db
from app.main import app
from app.models.asset import Asset
from app.models.project import Project
from app.models.scene import Scene


@pytest.fixture
def api(tmp_path, monkeypatch):
    app_data_dir = tmp_path / "app-data"
    monkeypatch.setenv("APP_DATA_DIR", str(app_data_dir))
    database_engine = create_engine_for_path(app_data_dir / "ai_director.db")
    init_db(database_engine)
    session_factory = create_session_factory(database_engine)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def request(method: str, path: str, data: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.request(method, path, data=data, files=files)

        return asyncio.run(send())

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield request, session_factory, app_data_dir
    finally:
        app.dependency_overrides.pop(get_db, None)
        database_engine.dispose()


def _project(session_factory, name: str) -> Project:
    with session_factory() as session:
        project = Project(
            name=name,
            description=None,
            aspect_ratio="9:16",
            width=1080,
            height=1920,
            fps=30,
        )
        session.add(project)
        session.commit()
        session.refresh(project)
        return project


def _scene(session_factory, project_id: str) -> Scene:
    with session_factory() as session:
        scene = Scene(
            project_id=project_id,
            scene_number=1,
            title="Asset Scene",
            duration_seconds=2,
        )
        session.add(scene)
        session.commit()
        session.refresh(scene)
        return scene


def _upload(request, project_id: str, filename: str = "frame.png", content: bytes = b"abcdef", **data) -> httpx.Response:
    form_data = {"type": "image", "role": "first_frame"}
    form_data.update(data)
    return request(
        "POST",
        f"/api/v1/projects/{project_id}/assets/upload",
        form_data,
        {"file": (filename, content, "image/png")},
    )


def test_upload_image_creates_project_level_asset_and_file(api) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory, "Upload project")

    response = _upload(request, project.id)

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    asset = body["data"]
    assert asset["project_id"] == project.id
    assert asset["scene_id"] is None
    assert asset["relative_path"].startswith("images/")
    assert not Path(asset["relative_path"]).is_absolute()
    assert asset["size_bytes"] == 6
    assert asset["mime_type"] == "image/png"

    stored_path = app_data_dir / "projects" / project.id / asset["relative_path"]
    assert stored_path.read_bytes() == b"abcdef"
    with session_factory() as session:
        persisted = session.get(Asset, asset["id"])
        assert persisted is not None
        assert persisted.relative_path == asset["relative_path"]


@pytest.mark.parametrize("filename", ["一二参考图 01.png", "first frame 01.png"])
def test_upload_supports_unicode_and_space_filenames(api, filename: str) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory, "Filename project")

    response = _upload(request, project.id, filename=filename)

    assert response.status_code == 200
    asset = response.json()["data"]
    stored_path = app_data_dir / "projects" / project.id / asset["relative_path"]
    assert stored_path.exists()
    assert stored_path.suffix == ".png"


def test_upload_scene_asset_requires_scene_in_current_project(api) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory, "Scene project")
    other_project = _project(session_factory, "Other project")
    scene = _scene(session_factory, project.id)
    other_scene = _scene(session_factory, other_project.id)

    success = _upload(request, project.id, scene_id=scene.id)
    assert success.status_code == 200
    assert success.json()["data"]["scene_id"] == scene.id

    missing = _upload(request, project.id, scene_id="missing-scene")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "SCENE_NOT_FOUND"

    mismatch = _upload(request, project.id, scene_id=other_scene.id)
    assert mismatch.status_code == 400
    assert mismatch.json()["error"]["code"] == "ASSET_SCENE_PROJECT_MISMATCH"

    with session_factory() as session:
        assert session.query(Asset).count() == 1
    assert list((app_data_dir / "projects" / project.id / "images").glob("*.tmp")) == []


def test_upload_rejects_missing_project_and_invalid_type_without_writing_files(api) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory, "Validation project")

    missing_project = _upload(request, "missing-project")
    assert missing_project.status_code == 404
    assert missing_project.json()["error"]["code"] == "PROJECT_NOT_FOUND"
    assert not (app_data_dir / "projects" / "missing-project").exists()

    invalid_type = _upload(request, project.id, type="unknown")
    assert invalid_type.status_code == 422
    assert not (app_data_dir / "projects" / project.id).exists()
    with session_factory() as session:
        assert session.query(Asset).count() == 0


def test_upload_uses_unique_safe_paths_for_duplicate_and_traversal_filenames(api) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory, "Safe path project")

    first = _upload(request, project.id, filename="duplicate.png")
    second = _upload(request, project.id, filename="duplicate.png")
    traversal = _upload(request, project.id, filename="..\\..\\evil.png")

    assert first.status_code == second.status_code == traversal.status_code == 200
    assets = [response.json()["data"] for response in (first, second, traversal)]
    assert len({asset["relative_path"] for asset in assets}) == 3
    asset_root = (app_data_dir / "projects" / project.id).resolve()
    for asset in assets:
        stored_path = (asset_root / asset["relative_path"]).resolve()
        assert stored_path.is_relative_to(asset_root)
        assert stored_path.exists()
        assert ".." not in Path(asset["relative_path"]).parts


def test_upload_removes_final_file_when_database_commit_fails(api, monkeypatch) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory, "Commit failure project")

    def fail_commit(_self) -> None:
        raise SQLAlchemyError("commit failed")

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = _upload(request, project.id)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "ASSET_UPLOAD_FAILED"
    assert list((app_data_dir / "projects" / project.id / "images").glob("*")) == []
    with session_factory() as session:
        assert session.query(Asset).count() == 0
