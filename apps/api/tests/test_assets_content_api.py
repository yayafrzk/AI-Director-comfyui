import asyncio
from pathlib import Path

import httpx
import pytest

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory, get_db
from app.main import app
from app.models.asset import Asset
from app.models.project import Project


@pytest.fixture
def api(tmp_path, monkeypatch):
    app_data_dir = tmp_path / "素材数据"
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

    def request(method: str, path: str) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.request(method, path)

        return asyncio.run(send())

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield request, session_factory, app_data_dir
    finally:
        app.dependency_overrides.pop(get_db, None)
        database_engine.dispose()


def _project(session_factory) -> Project:
    with session_factory() as session:
        project = Project(
            name="Content project",
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


def _asset(session_factory, project_id: str, relative_path: str, mime_type: str, **overrides) -> Asset:
    values = {
        "project_id": project_id,
        "scene_id": None,
        "type": "image",
        "role": "first_frame",
        "relative_path": relative_path,
        "thumbnail_path": None,
        "mime_type": mime_type,
        "width": None,
        "height": None,
        "duration_seconds": None,
        "size_bytes": 0,
        "hash": None,
    }
    values.update(overrides)
    with session_factory() as session:
        asset = Asset(**values)
        session.add(asset)
        session.commit()
        session.refresh(asset)
        return asset


def _write_asset_file(app_data_dir: Path, asset: Asset, content: bytes) -> Path:
    path = app_data_dir / "projects" / asset.project_id / asset.relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_get_asset_metadata_and_missing_asset(api) -> None:
    request, session_factory, _ = api
    project = _project(session_factory)
    asset = _asset(session_factory, project.id, "images/frame.png", "image/png", size_bytes=12)

    response = request("GET", f"/api/v1/assets/{asset.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["id"] == asset.id
    assert body["data"]["project_id"] == project.id
    assert body["data"]["scene_id"] is None
    assert body["data"]["type"] == "image"
    assert body["data"]["role"] == "first_frame"
    assert body["data"]["relative_path"] == "images/frame.png"
    assert body["data"]["mime_type"] == "image/png"
    assert body["data"]["size_bytes"] == 12
    assert body["data"]["created_at"]

    missing = request("GET", "/api/v1/assets/missing-asset")
    assert missing.status_code == 404
    assert missing.json()["error"] == {"code": "ASSET_NOT_FOUND", "message": "Asset not found"}


@pytest.mark.parametrize(
    ("asset_type", "relative_path", "mime_type", "content"),
    [
        ("image", "images/frame.png", "image/png", b"image-content"),
        ("video", "videos/clip.mp4", "video/mp4", b"video-content"),
        ("audio", "audio/voice.wav", "audio/wav", b"audio-content"),
    ],
)
def test_get_asset_content_returns_file_and_mime_type(api, asset_type, relative_path, mime_type, content) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory)
    asset = _asset(
        session_factory,
        project.id,
        relative_path,
        mime_type,
        type=asset_type,
        role="output",
        size_bytes=len(content),
    )
    _write_asset_file(app_data_dir, asset, content)

    response = request("GET", f"/api/v1/assets/{asset.id}/content")

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"].startswith(mime_type)


def test_missing_asset_file_keeps_metadata_available(api) -> None:
    request, session_factory, _ = api
    project = _project(session_factory)
    asset = _asset(session_factory, project.id, "images/missing.png", "image/png")

    metadata = request("GET", f"/api/v1/assets/{asset.id}")
    assert metadata.status_code == 200

    content = request("GET", f"/api/v1/assets/{asset.id}/content")
    assert content.status_code == 404
    assert content.json()["error"] == {
        "code": "ASSET_FILE_NOT_FOUND",
        "message": "Asset file not found",
    }


@pytest.mark.parametrize("relative_path", ["../../outside.txt", "..\\..\\outside.txt"])
def test_content_rejects_unix_and_windows_traversal(api, relative_path: str) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory)
    asset = _asset(session_factory, project.id, relative_path, "text/plain")
    (app_data_dir / "outside.txt").write_bytes(b"outside-content")

    response = request("GET", f"/api/v1/assets/{asset.id}/content")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ASSET_FILE_INVALID"
    assert response.content != b"outside-content"


def test_content_rejects_absolute_path(api) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory)
    outside_path = app_data_dir / "outside.txt"
    outside_path.write_bytes(b"outside-content")
    asset = _asset(session_factory, project.id, str(outside_path), "text/plain")

    response = request("GET", f"/api/v1/assets/{asset.id}/content")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ASSET_FILE_INVALID"
    assert response.content != b"outside-content"
