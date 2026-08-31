import asyncio
from pathlib import Path

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
    app_data_dir = tmp_path / "导出 数据"
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
            name="Export project",
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


def _scene(session_factory, project_id: str, scene_number: int, title: str) -> Scene:
    with session_factory() as session:
        scene = Scene(
            project_id=project_id,
            scene_number=scene_number,
            title=title,
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


def _asset(
    session_factory,
    app_data_dir: Path,
    project_id: str,
    scene_id: str,
    relative_path: str,
    content: bytes | None = None,
) -> Asset:
    with session_factory() as session:
        asset = Asset(
            project_id=project_id,
            scene_id=scene_id,
            type="video",
            role="output",
            relative_path=relative_path,
            thumbnail_path=None,
            mime_type="video/mp4",
            width=None,
            height=None,
            duration_seconds=None,
            size_bytes=len(content or b""),
            hash=None,
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
    if content is not None:
        source_path = app_data_dir / "projects" / project_id / relative_path
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(content)
    return asset


def _select(session_factory, scene_id: str, asset_id: str) -> None:
    with session_factory() as session:
        scene = session.get(Scene, scene_id)
        assert scene is not None
        scene.selected_asset_id = asset_id
        session.commit()


def _export_root(app_data_dir: Path, project_id: str) -> Path:
    return app_data_dir / "projects" / project_id / "exports"


def _export_directories(app_data_dir: Path, project_id: str) -> list[Path]:
    root = _export_root(app_data_dir, project_id)
    return list(root.iterdir()) if root.exists() else []


def test_export_copies_selected_versions_in_scene_number_order(api) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory)
    scene_two = _scene(session_factory, project.id, 2, "第二幕")
    scene_one = _scene(session_factory, project.id, 1, "第一幕")
    scene_three = _scene(session_factory, project.id, 3, "第三幕")
    selected_two = _asset(session_factory, app_data_dir, project.id, scene_two.id, "videos/two.mp4", b"two")
    selected_one = _asset(session_factory, app_data_dir, project.id, scene_one.id, "videos/one.mp4", b"one")
    selected_three = _asset(session_factory, app_data_dir, project.id, scene_three.id, "videos/three.webp", b"three")
    _asset(session_factory, app_data_dir, project.id, scene_one.id, "videos/not-selected.mp4", b"unused")
    _select(session_factory, scene_two.id, selected_two.id)
    _select(session_factory, scene_one.id, selected_one.id)
    _select(session_factory, scene_three.id, selected_three.id)

    response = request("POST", f"/api/v1/projects/{project.id}/export")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    data = body["data"]
    assert data["project_id"] == project.id
    assert not Path(data["export_dir"]).is_absolute()
    assert [file["scene_number"] for file in data["files"]] == [1, 2, 3]
    assert [file["asset_id"] for file in data["files"]] == [selected_one.id, selected_two.id, selected_three.id]
    export_directory = app_data_dir / data["export_dir"]
    assert [path.name for path in export_directory.iterdir()] == [
        "01_第一幕.mp4",
        "02_第二幕.mp4",
        "03_第三幕.webp",
    ]
    assert (export_directory / "01_第一幕.mp4").read_bytes() == b"one"
    assert not (export_directory / "01_not-selected.mp4").exists()


@pytest.mark.parametrize(
    ("kind", "error_code"),
    [
        ("missing_selection", "SCENE_SELECTED_ASSET_MISSING"),
        ("invalid_selection", "SCENE_SELECTED_ASSET_INVALID"),
        ("missing_file", "ASSET_FILE_NOT_FOUND"),
        ("invalid_suffix", "ASSET_PATH_INVALID"),
        ("traversal_unix", "ASSET_PATH_INVALID"),
        ("traversal_windows", "ASSET_PATH_INVALID"),
        ("absolute", "ASSET_PATH_INVALID"),
    ],
)
def test_export_validates_all_selected_assets_before_creating_output(api, kind: str, error_code: str) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory)
    first_scene = _scene(session_factory, project.id, 1, "Valid first")
    first_asset = _asset(session_factory, app_data_dir, project.id, first_scene.id, "videos/first.mp4", b"first")
    _select(session_factory, first_scene.id, first_asset.id)
    second_scene = _scene(session_factory, project.id, 2, "Invalid second")

    if kind == "invalid_selection":
        other_scene = _scene(session_factory, project.id, 3, "Other")
        other_asset = _asset(session_factory, app_data_dir, project.id, other_scene.id, "videos/other.mp4", b"other")
        _select(session_factory, second_scene.id, other_asset.id)
    elif kind == "missing_file":
        asset = _asset(session_factory, app_data_dir, project.id, second_scene.id, "videos/missing.mp4")
        _select(session_factory, second_scene.id, asset.id)
    elif kind == "invalid_suffix":
        asset = _asset(session_factory, app_data_dir, project.id, second_scene.id, "videos/invalid.m-p4", b"invalid")
        _select(session_factory, second_scene.id, asset.id)
    elif kind == "traversal_unix":
        (app_data_dir / "outside.mp4").write_bytes(b"outside")
        asset = _asset(session_factory, app_data_dir, project.id, second_scene.id, "../../outside.mp4")
        _select(session_factory, second_scene.id, asset.id)
    elif kind == "traversal_windows":
        asset = _asset(session_factory, app_data_dir, project.id, second_scene.id, "..\\..\\outside.mp4")
        _select(session_factory, second_scene.id, asset.id)
    elif kind == "absolute":
        asset = _asset(session_factory, app_data_dir, project.id, second_scene.id, "C:\\evil.mp4")
        _select(session_factory, second_scene.id, asset.id)

    response = request("POST", f"/api/v1/projects/{project.id}/export")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == error_code
    assert _export_directories(app_data_dir, project.id) == []


def test_export_rejects_selected_asset_from_another_project(api) -> None:
    request, session_factory, app_data_dir = api
    project_a = _project(session_factory)
    scene_a = _scene(session_factory, project_a.id, 1, "Scene A")
    project_b = _project(session_factory)
    scene_b = _scene(session_factory, project_b.id, 1, "Scene B")
    asset_b = _asset(session_factory, app_data_dir, project_b.id, scene_b.id, "videos/project-b.mp4", b"project-b")
    _select(session_factory, scene_a.id, asset_b.id)

    response = request("POST", f"/api/v1/projects/{project_a.id}/export")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SCENE_SELECTED_ASSET_INVALID"
    assert _export_directories(app_data_dir, project_a.id) == []


def test_export_rejects_symlink_escape(api) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory)
    scene = _scene(session_factory, project.id, 1, "Symlink")
    outside_directory = app_data_dir / "outside"
    outside_directory.mkdir(parents=True)
    (outside_directory / "escape.mp4").write_bytes(b"outside")
    link = app_data_dir / "projects" / project.id / "videos" / "linked"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside_directory, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Symlink creation is not permitted: {error}")

    asset = _asset(session_factory, app_data_dir, project.id, scene.id, "videos/linked/escape.mp4")
    _select(session_factory, scene.id, asset.id)

    response = request("POST", f"/api/v1/projects/{project.id}/export")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ASSET_PATH_INVALID"
    assert _export_directories(app_data_dir, project.id) == []
def test_export_sanitizes_titles_and_falls_back_for_empty_title(api) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory)
    unsafe = _scene(session_factory, project.id, 1, '  中文:<bad>|title?* . ')
    empty = _scene(session_factory, project.id, 2, ' . ')
    unsafe_asset = _asset(session_factory, app_data_dir, project.id, unsafe.id, "videos/unsafe.mp4", b"unsafe")
    empty_asset = _asset(session_factory, app_data_dir, project.id, empty.id, "videos/empty.mp4", b"empty")
    _select(session_factory, unsafe.id, unsafe_asset.id)
    _select(session_factory, empty.id, empty_asset.id)

    response = request("POST", f"/api/v1/projects/{project.id}/export")

    assert response.status_code == 200
    filenames = [file["filename"] for file in response.json()["data"]["files"]]
    assert filenames == ["01_中文badtitle.mp4", "02_scene.mp4"]
    assert all(not set('<>:"/\\|?*').intersection(filename) for filename in filenames)


def test_export_creates_unique_directories_and_preserves_existing_export(api) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory)
    scene = _scene(session_factory, project.id, 1, "Repeat")
    asset = _asset(session_factory, app_data_dir, project.id, scene.id, "videos/repeat.mp4", b"repeat")
    _select(session_factory, scene.id, asset.id)

    first = request("POST", f"/api/v1/projects/{project.id}/export").json()["data"]
    second = request("POST", f"/api/v1/projects/{project.id}/export").json()["data"]

    assert first["export_id"] != second["export_id"]
    first_directory = app_data_dir / first["export_dir"]
    second_directory = app_data_dir / second["export_dir"]
    assert first_directory != second_directory
    assert (first_directory / "01_Repeat.mp4").read_bytes() == b"repeat"
    assert (second_directory / "01_Repeat.mp4").read_bytes() == b"repeat"


def test_export_missing_project_and_empty_project(api) -> None:
    request, session_factory, app_data_dir = api

    missing = request("POST", "/api/v1/projects/missing-project/export")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    project = _project(session_factory)
    empty = request("POST", f"/api/v1/projects/{project.id}/export")
    assert empty.status_code == 200
    empty_data = empty.json()["data"]
    assert empty_data["files"] == []
    assert (app_data_dir / empty_data["export_dir"]).is_dir()


def test_export_copy_failure_removes_files_created_for_this_export(api, monkeypatch) -> None:
    request, session_factory, app_data_dir = api
    project = _project(session_factory)
    first_scene = _scene(session_factory, project.id, 1, "First")
    second_scene = _scene(session_factory, project.id, 2, "Second")
    first_asset = _asset(session_factory, app_data_dir, project.id, first_scene.id, "videos/first.mp4", b"first")
    second_asset = _asset(session_factory, app_data_dir, project.id, second_scene.id, "videos/second.mp4", b"second")
    _select(session_factory, first_scene.id, first_asset.id)
    _select(session_factory, second_scene.id, second_asset.id)

    historical_export = request("POST", f"/api/v1/projects/{project.id}/export").json()["data"]
    historical_directory = app_data_dir / historical_export["export_dir"]
    historical_files = sorted(path.name for path in historical_directory.iterdir())

    from app.services import export_service

    copy_count = 0
    original_copy2 = export_service.shutil.copy2

    def fail_on_second_copy(source, destination):
        nonlocal copy_count
        copy_count += 1
        if copy_count == 2:
            raise OSError("disk full")
        return original_copy2(source, destination)

    monkeypatch.setattr(export_service.shutil, "copy2", fail_on_second_copy)
    response = request("POST", f"/api/v1/projects/{project.id}/export")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "EXPORT_FAILED"
    assert copy_count == 2
    assert sorted(path.name for path in _export_directories(app_data_dir, project.id)) == [historical_export["export_id"]]
    assert sorted(path.name for path in historical_directory.iterdir()) == historical_files