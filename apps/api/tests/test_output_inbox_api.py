import asyncio
import os
import time
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory, get_db
from app.main import app
from app.models.asset import Asset
from app.models.generation_job import GenerationJob
from app.models.generation_output import GenerationOutput
from app.models.project import Project
from app.models.scene import Scene
from app.models.workflow_template import WorkflowTemplate
from app.services.media_metadata import VideoMetadata, VideoMetadataProbeError
from app.services.system_workflows import MANUAL_IMPORT_WORKFLOW_SLUG


@pytest.fixture
def api(tmp_path, monkeypatch):
    app_data_dir = tmp_path / "app-data"
    monkeypatch.setenv("APP_DATA_DIR", str(app_data_dir))
    engine = create_engine_for_path(app_data_dir / "ai_director.db")
    init_db(engine)
    session_factory = create_session_factory(engine)
    output_dir = tmp_path / "ComfyUI output 空格"
    output_dir.mkdir()

    def override_get_db():
        with session_factory() as session:
            yield session

    def request(method: str, path: str, json: dict | None = None) -> httpx.Response:
        async def send() -> httpx.Response:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                return await client.request(method, path, json=json)

        return asyncio.run(send())

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield request, session_factory, app_data_dir, output_dir
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def _configure(request, output_dir: Path) -> None:
    response = request("PUT", "/api/v1/output-inbox/settings", {"output_dir": str(output_dir)})
    assert response.status_code == 200


def _file(output_dir: Path, relative_path: str, content: bytes = b"media", age: int = 10) -> Path:
    path = output_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    timestamp_ns = time.time_ns() - age * 1_000_000_000
    os.utime(path, ns=(timestamp_ns, timestamp_ns))
    return path


def _scene(session_factory) -> tuple[Project, Scene]:
    with session_factory() as session:
        project = Project(name="Inbox project", description=None, aspect_ratio="16:9", width=1920, height=1080, fps=24)
        session.add(project)
        session.flush()
        scene = Scene(
            project_id=project.id,
            scene_number=1,
            title="Scene 01",
            description=None,
            prompt="scene prompt",
            negative_prompt="scene negative",
            seed=321,
            duration_seconds=5,
            megapixels=0.6,
            workflow_template_id=None,
            selected_asset_id=None,
            status="draft",
        )
        session.add(scene)
        session.commit()
        session.refresh(project)
        session.refresh(scene)
        return project, scene


def _import(request, scene_id: str, relative_path: str, **overrides) -> httpx.Response:
    return request(
        "POST",
        f"/api/v1/scenes/{scene_id}/output-inbox/import",
        {"relative_path": relative_path, **overrides},
    )


def _count(session_factory, model) -> int:
    with session_factory() as session:
        return session.query(model).count()


def _mock_video(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.manual_result_import.probe_video_metadata",
        lambda _path: VideoMetadata(width=1280, height=720, duration_seconds=5.17),
    )
    monkeypatch.setattr(
        "app.services.manual_result_import.generate_video_thumbnail",
        lambda _source, thumbnail, _duration: thumbnail.write_bytes(b"thumbnail"),
    )


def test_settings_unconfigured_and_items_reject_unconfigured(api) -> None:
    request, _, _, _ = api
    settings = request("GET", "/api/v1/output-inbox/settings")
    assert settings.status_code == 200
    assert settings.json() == {"data": {"configured": False, "output_dir": None}, "error": None}
    items = request("GET", "/api/v1/output-inbox/items")
    assert items.status_code == 400
    assert items.json()["error"]["code"] == "OUTPUT_INBOX_NOT_CONFIGURED"


def test_settings_persist_absolute_directory_as_utf8_json(api) -> None:
    request, _, app_data_dir, output_dir = api
    _configure(request, output_dir)
    response = request("GET", "/api/v1/output-inbox/settings")
    assert response.status_code == 200
    assert response.json()["data"] == {"configured": True, "output_dir": str(output_dir.resolve())}
    settings_file = app_data_dir / "settings" / "output_inbox.json"
    assert 'ComfyUI output 空格' in settings_file.read_text(encoding="utf-8")
    assert list(settings_file.parent.glob("*.tmp")) == []


@pytest.mark.parametrize("path_kind", ["relative", "missing", "file", "empty"])
def test_settings_reject_invalid_directory(api, tmp_path, path_kind) -> None:
    request, _, _, output_dir = api
    file_path = output_dir / "not-a-directory.txt"
    file_path.write_text("x", encoding="utf-8")
    paths = {
        "relative": "ComfyUI/output",
        "missing": str(tmp_path / "missing"),
        "file": str(file_path),
        "empty": "  ",
    }
    response = request("PUT", "/api/v1/output-inbox/settings", {"output_dir": paths[path_kind]})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "OUTPUT_INBOX_DIRECTORY_INVALID"


def test_list_recurses_filters_sorts_limits_and_uses_relative_paths(api) -> None:
    request, _, _, output_dir = api
    _configure(request, output_dir)
    _file(output_dir, "old.mp4", b"old", age=40)
    _file(output_dir, "newest.MP4", b"newest", age=10)
    _file(output_dir, "picture.png", b"image", age=30)
    _file(output_dir, "H3/中文 clip.webm", b"nested", age=20)
    _file(output_dir, "note.txt", b"ignore", age=5)

    response = request("GET", "/api/v1/output-inbox/items")
    assert response.status_code == 200
    items = response.json()["data"]
    assert [item["relative_path"] for item in items] == [
        "newest.MP4", "H3/中文 clip.webm", "picture.png", "old.mp4"
    ]
    assert [item["type"] for item in items] == ["video", "video", "image", "video"]
    assert items[0]["size_bytes"] == 6
    assert all(item["archived"] is False and item["archived_scene_id"] is None for item in items)
    assert all(str(output_dir) not in str(item) for item in items)
    limited = request("GET", "/api/v1/output-inbox/items?limit=2")
    assert [item["id"] for item in limited.json()["data"]] == [item["id"] for item in items[:2]]


def test_preview_reads_supported_nested_file_without_copying(api) -> None:
    request, session_factory, app_data_dir, output_dir = api
    _configure(request, output_dir)
    _file(output_dir, "H3/clip.webm", b"original bytes")

    response = request("GET", "/api/v1/output-inbox/content?path=H3%2Fclip.webm")
    assert response.status_code == 200
    assert response.content == b"original bytes"
    assert response.headers["content-type"].startswith("video/webm")
    assert _count(session_factory, Asset) == 0
    assert not (app_data_dir / "projects").exists()


@pytest.mark.parametrize("bad_path", ["../outside.mp4", "../../outside.png", "/etc/passwd", "C:\\Windows\\win.ini", "..\\outside.mp4"])
def test_preview_rejects_path_escape(api, bad_path) -> None:
    request, _, _, output_dir = api
    _configure(request, output_dir)
    response = request("GET", "/api/v1/output-inbox/content?path=" + quote(bad_path, safe=""))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "OUTPUT_INBOX_PATH_INVALID"


def test_preview_missing_and_unsupported(api) -> None:
    request, _, _, output_dir = api
    _configure(request, output_dir)
    _file(output_dir, "notes.txt")
    missing = request("GET", "/api/v1/output-inbox/content?path=missing.mp4")
    unsupported = request("GET", "/api/v1/output-inbox/content?path=notes.txt")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "OUTPUT_INBOX_ITEM_NOT_FOUND"
    assert unsupported.status_code == 400
    assert unsupported.json()["error"]["code"] == "OUTPUT_INBOX_TYPE_UNSUPPORTED"


def test_symlink_escape_is_not_listed_or_previewed(api, tmp_path) -> None:
    request, _, _, output_dir = api
    _configure(request, output_dir)
    outside = _file(tmp_path, "outside.mp4")
    link = output_dir / "link.mp4"
    try:
        link.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"OS denied symlink creation: {error}")
    assert request("GET", "/api/v1/output-inbox/items").json()["data"] == []
    response = request("GET", "/api/v1/output-inbox/content?path=link.mp4")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "OUTPUT_INBOX_PATH_INVALID"


def test_video_import_copies_source_creates_version_and_marks_archived(api, monkeypatch) -> None:
    request, session_factory, app_data_dir, output_dir = api
    _configure(request, output_dir)
    project, scene = _scene(session_factory)
    source = _file(output_dir, "H3/clip.mp4", b"original video")
    original_stat = source.stat()
    _mock_video(monkeypatch)
    item = request("GET", "/api/v1/output-inbox/items").json()["data"][0]

    response = _import(request, scene.id, "H3/clip.mp4")
    assert response.status_code == 201
    job = response.json()["data"]
    assert job["status"] == "completed"
    assert job["prompt_snapshot"] == "scene prompt"
    assert job["negative_prompt_snapshot"] == "scene negative"
    assert job["seed"] is None
    assert job["comfy_prompt_id"] is None
    assert job["params_json"] == {
        "source": "comfyui_output_inbox",
        "source_filename": "clip.mp4",
        "source_relative_path": "H3/clip.mp4",
        "source_inbox_id": item["id"],
        "source_size_bytes": original_stat.st_size,
        "source_mtime_ns": original_stat.st_mtime_ns,
        "duration_seconds": 5.0,
        "megapixels": 0.6,
    }
    assert len(job["outputs"]) == 1
    output = job["outputs"][0]
    assert output["output_index"] == 0
    asset = output["asset"]
    assert asset["type"] == "video" and asset["role"] == "output"
    assert asset["duration_seconds"] == 5.17
    assert (app_data_dir / "projects" / project.id / asset["relative_path"]).read_bytes() == b"original video"
    assert (app_data_dir / "projects" / project.id / asset["thumbnail_path"]).read_bytes() == b"thumbnail"
    assert source.read_bytes() == b"original video"
    assert source.stat().st_mtime_ns == original_stat.st_mtime_ns
    with session_factory() as session:
        saved_scene = session.get(Scene, scene.id)
        assert saved_scene is not None and saved_scene.selected_asset_id is None
        assert session.query(GenerationOutput).count() == 1
        assert session.query(WorkflowTemplate).filter_by(slug=MANUAL_IMPORT_WORKFLOW_SLUG).count() == 1
    refreshed = request("GET", "/api/v1/output-inbox/items").json()["data"][0]
    assert refreshed["archived"] is True
    assert refreshed["archived_scene_id"] == scene.id
    duplicate = _import(request, scene.id, "H3/clip.mp4")
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "OUTPUT_INBOX_ITEM_ALREADY_ARCHIVED"
    assert _count(session_factory, GenerationJob) == 1


def test_image_import_uses_explicit_snapshots_and_optional_final_selection(api) -> None:
    request, session_factory, app_data_dir, output_dir = api
    _configure(request, output_dir)
    project, scene = _scene(session_factory)
    source = _file(output_dir, "picture.PNG", b"picture bytes")

    response = _import(
        request,
        scene.id,
        "picture.PNG",
        prompt_snapshot="Comfy prompt",
        negative_prompt_snapshot="Comfy negative",
        select_as_final=True,
    )
    assert response.status_code == 201
    job = response.json()["data"]
    assert job["prompt_snapshot"] == "Comfy prompt"
    assert job["negative_prompt_snapshot"] == "Comfy negative"
    assert job["seed"] is None
    asset = job["outputs"][0]["asset"]
    assert asset["type"] == "image"
    assert (app_data_dir / "projects" / project.id / asset["relative_path"]).read_bytes() == b"picture bytes"
    assert source.read_bytes() == b"picture bytes"
    with session_factory() as session:
        saved_scene = session.get(Scene, scene.id)
        assert saved_scene is not None and saved_scene.selected_asset_id == asset["id"]


def test_import_rejects_missing_scene_source_and_path_escape(api) -> None:
    request, session_factory, _, output_dir = api
    _configure(request, output_dir)
    _, scene = _scene(session_factory)
    missing_scene = _import(request, "missing", "clip.mp4")
    missing_source = _import(request, scene.id, "missing.mp4")
    escape = _import(request, scene.id, "../outside.mp4")
    assert (missing_scene.status_code, missing_scene.json()["error"]["code"]) == (404, "SCENE_NOT_FOUND")
    assert (missing_source.status_code, missing_source.json()["error"]["code"]) == (404, "OUTPUT_INBOX_ITEM_NOT_FOUND")
    assert (escape.status_code, escape.json()["error"]["code"]) == (400, "OUTPUT_INBOX_PATH_INVALID")
    assert _count(session_factory, GenerationJob) == 0


def test_import_rejects_recently_modified_file_without_copy(api) -> None:
    request, session_factory, app_data_dir, output_dir = api
    _configure(request, output_dir)
    project, scene = _scene(session_factory)
    source = _file(output_dir, "writing.mp4", age=0)
    response = _import(request, scene.id, "writing.mp4")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OUTPUT_INBOX_ITEM_BUSY"
    assert source.read_bytes() == b"media"
    assert not (app_data_dir / "projects" / project.id).exists()


def test_metadata_failure_cleans_project_copy_and_keeps_source(api, monkeypatch) -> None:
    request, session_factory, app_data_dir, output_dir = api
    _configure(request, output_dir)
    project, scene = _scene(session_factory)
    source = _file(output_dir, "broken.mp4", b"source bytes")

    def fail_metadata(_path):
        raise VideoMetadataProbeError("invalid video")

    monkeypatch.setattr("app.services.manual_result_import.probe_video_metadata", fail_metadata)
    response = _import(request, scene.id, "broken.mp4")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ASSET_MEDIA_INVALID"
    assert source.read_bytes() == b"source bytes"
    assert list((app_data_dir / "projects" / project.id / "videos").glob("*")) == []
    assert _count(session_factory, Asset) == 0
    assert _count(session_factory, GenerationOutput) == 0
    assert _count(session_factory, GenerationJob) == 0


def test_database_failure_rolls_back_and_cleans_copy(api, monkeypatch) -> None:
    request, session_factory, app_data_dir, output_dir = api
    _configure(request, output_dir)
    project, scene = _scene(session_factory)
    source = _file(output_dir, "result.png", b"source bytes")

    def fail_commit(_self) -> None:
        raise SQLAlchemyError("commit failed")

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = _import(request, scene.id, "result.png")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "MANUAL_RESULT_IMPORT_FAILED"
    assert source.read_bytes() == b"source bytes"
    assert list((app_data_dir / "projects" / project.id / "images").glob("*")) == []
    assert _count(session_factory, Asset) == 0
    assert _count(session_factory, GenerationOutput) == 0
    assert _count(session_factory, GenerationJob) == 0


def test_failed_settings_replace_preserves_previous_directory(api, tmp_path, monkeypatch) -> None:
    request, _, app_data_dir, output_dir = api
    _configure(request, output_dir)
    replacement_dir = tmp_path / "second-output"
    replacement_dir.mkdir()

    def fail_replace(_source, _target) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr("app.services.output_inbox_settings.os.replace", fail_replace)
    response = request("PUT", "/api/v1/output-inbox/settings", {"output_dir": str(replacement_dir)})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "OUTPUT_INBOX_SETTINGS_FAILED"
    current = request("GET", "/api/v1/output-inbox/settings")
    assert current.json()["data"]["output_dir"] == str(output_dir.resolve())
    assert list((app_data_dir / "settings").glob("*.tmp")) == []


def test_import_rejects_source_changed_during_copy_and_cleans_copy(api, monkeypatch) -> None:
    request, session_factory, app_data_dir, output_dir = api
    _configure(request, output_dir)
    project, scene = _scene(session_factory)
    source = _file(output_dir, "changing.png", b"first version")
    from app.services.storage_assets import store_asset_path

    def copy_then_change(project_id, asset_type, source_path, filename):
        stored = store_asset_path(project_id, asset_type, source_path, filename)
        source.write_bytes(b"second version")
        return stored

    monkeypatch.setattr("app.services.output_inbox.store_asset_path", copy_then_change)
    response = _import(request, scene.id, "changing.png")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OUTPUT_INBOX_ITEM_BUSY"
    assert list((app_data_dir / "projects" / project.id / "images").glob("*")) == []
    assert _count(session_factory, GenerationJob) == 0
    assert _count(session_factory, Asset) == 0
    assert _count(session_factory, GenerationOutput) == 0


def test_copy_failure_cleans_temporary_file_and_keeps_source(api, monkeypatch) -> None:
    request, session_factory, app_data_dir, output_dir = api
    _configure(request, output_dir)
    project, scene = _scene(session_factory)
    source = _file(output_dir, "disk-full.png", b"source bytes")

    def fail_copy(_source, _destination, _length) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.services.storage_assets.shutil.copyfileobj", fail_copy)
    response = _import(request, scene.id, "disk-full.png")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "OUTPUT_INBOX_IMPORT_FAILED"
    assert source.read_bytes() == b"source bytes"
    assert list((app_data_dir / "projects" / project.id / "images").glob("*")) == []
    assert _count(session_factory, GenerationJob) == 0
    assert _count(session_factory, Asset) == 0
    assert _count(session_factory, GenerationOutput) == 0
