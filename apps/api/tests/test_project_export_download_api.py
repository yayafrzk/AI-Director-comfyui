import asyncio
import io
import zipfile
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory, get_db
from app.main import app
from app.models.asset import Asset
from app.models.project import Project
from app.models.scene import Scene


@pytest.fixture
def api(tmp_path, monkeypatch):
    app_data_dir = tmp_path / "下载 数据"
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
            name="Download project",
            description=None,
            aspect_ratio="16:9",
            width=1920,
            height=1080,
            fps=24,
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
            title="一二来到湖边",
            description=None,
            prompt=None,
            negative_prompt=None,
            seed=None,
            duration_seconds=5.0,
            workflow_template_id=None,
            selected_asset_id=None,
            status="draft",
        )
        session.add(scene)
        session.commit()
        session.refresh(scene)
        return scene


def _asset(session_factory, app_data_dir: Path, project_id: str, scene_id: str) -> Asset:
    content = b"video-content"
    with session_factory() as session:
        asset = Asset(
            project_id=project_id,
            scene_id=scene_id,
            type="video",
            role="output",
            relative_path="videos/private-source.mp4",
            thumbnail_path=None,
            mime_type="video/mp4",
            width=None,
            height=None,
            duration_seconds=None,
            size_bytes=len(content),
            hash=None,
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
    source_path = app_data_dir / "projects" / project_id / asset.relative_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(content)
    return asset


def _select(session_factory, scene_id: str, asset_id: str) -> None:
    with session_factory() as session:
        scene = session.get(Scene, scene_id)
        assert scene is not None
        scene.selected_asset_id = asset_id
        session.commit()


def _create_export(api) -> tuple[Project, dict, Path]:
    request, session_factory, app_data_dir = api
    project = _project(session_factory)
    scene = _scene(session_factory, project.id)
    asset = _asset(session_factory, app_data_dir, project.id, scene.id)
    _select(session_factory, scene.id, asset.id)
    response = request("POST", f"/api/v1/projects/{project.id}/export")
    assert response.status_code == 200
    export = response.json()["data"]
    return project, export, app_data_dir / export["export_dir"]


def _download_path(project_id: str, export_id: str) -> str:
    return f"/api/v1/projects/{project_id}/exports/{export_id}/download"


def test_download_returns_safe_zip_with_export_contents_and_cleans_temp_file(api) -> None:
    request, _session_factory, app_data_dir = api
    project, export, export_directory = _create_export(api)
    export_directories_before = sorted(path.name for path in export_directory.parent.iterdir())

    response = request("GET", _download_path(project.id, export["export_id"]))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert f'filename="export-{export["export_id"]}.zip"' in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert names == ["01_一二来到湖边.mp4", "manifest.json"]
        assert archive.read("01_一二来到湖边.mp4") == b"video-content"
        assert archive.read("manifest.json") == (export_directory / "manifest.json").read_bytes()
    assert all("/" not in name and "\\" not in name and ".." not in name for name in names)
    assert sorted(path.name for path in export_directory.parent.iterdir()) == export_directories_before
    temporary_directory = app_data_dir / "tmp" / "exports"
    assert list(temporary_directory.iterdir()) == []


def test_download_rejects_missing_project_invalid_id_and_missing_export(api) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory)

    missing_project = request("GET", _download_path(str(uuid4()), str(uuid4())))
    assert missing_project.status_code == 404
    assert missing_project.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    invalid_id = request("GET", _download_path(project.id, "not-a-uuid"))
    assert invalid_id.status_code == 400
    assert invalid_id.json()["error"]["code"] == "EXPORT_ID_INVALID"
    temporary_directory = app_data_dir / "tmp" / "exports"
    assert not temporary_directory.exists() or list(temporary_directory.iterdir()) == []

    missing_export = request("GET", _download_path(project.id, str(uuid4())))
    assert missing_export.status_code == 404
    assert missing_export.json()["error"]["code"] == "EXPORT_NOT_FOUND"


def test_download_rejects_missing_manifest_and_nested_directory(api) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory)
    missing_manifest_id = str(uuid4())
    (app_data_dir / "projects" / project.id / "exports" / missing_manifest_id).mkdir(parents=True)

    missing_manifest = request("GET", _download_path(project.id, missing_manifest_id))
    assert missing_manifest.status_code == 409
    assert missing_manifest.json()["error"]["code"] == "EXPORT_CONTENT_INVALID"

    project_with_export, export, export_directory = _create_export(api)
    (export_directory / "nested").mkdir()
    nested = request("GET", _download_path(project_with_export.id, export["export_id"]))
    assert nested.status_code == 409
    assert nested.json()["error"]["code"] == "EXPORT_CONTENT_INVALID"


def test_download_rejects_symlink_escape(api) -> None:
    request, _session_factory, app_data_dir = api
    project, export, export_directory = _create_export(api)
    outside_path = app_data_dir / "outside.mp4"
    outside_path.write_bytes(b"outside")
    link = export_directory / "evil.mp4"
    try:
        link.symlink_to(outside_path)
    except OSError as error:
        pytest.skip(f"Symlink creation is not permitted: {error}")

    response = request("GET", _download_path(project.id, export["export_id"]))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EXPORT_CONTENT_INVALID"


def test_download_zip_failure_keeps_export_and_removes_temp_zip(api, monkeypatch) -> None:
    request, _session_factory, app_data_dir = api
    project, export, export_directory = _create_export(api)
    original_files = sorted(path.name for path in export_directory.iterdir())

    from app.services import export_service

    def fail_write(self, filename, arcname=None, compress_type=None, compresslevel=None):
        raise OSError("disk full")

    monkeypatch.setattr(export_service.zipfile.ZipFile, "write", fail_write)
    response = request("GET", _download_path(project.id, export["export_id"]))

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "EXPORT_DOWNLOAD_FAILED"
    assert sorted(path.name for path in export_directory.iterdir()) == original_files
    temporary_directory = app_data_dir / "tmp" / "exports"
    assert list(temporary_directory.iterdir()) == []
