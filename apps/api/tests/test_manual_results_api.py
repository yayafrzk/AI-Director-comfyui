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
from app.models.generation_job import GenerationJob
from app.models.generation_output import GenerationOutput
from app.models.project import Project
from app.models.scene import Scene
from app.models.workflow_template import WorkflowTemplate
from app.services.media_metadata import FFprobeNotFoundError, VideoMetadata, VideoMetadataProbeError
from app.services.media_thumbnail import FFmpegNotFoundError, VideoThumbnailError
from app.services.system_workflows import MANUAL_IMPORT_WORKFLOW_SLUG


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

    def request(
        method: str,
        path: str,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> httpx.Response:
        async def send() -> httpx.Response:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                return await client.request(method, path, data=data, files=files)

        return asyncio.run(send())

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield request, session_factory, app_data_dir
    finally:
        app.dependency_overrides.pop(get_db, None)
        database_engine.dispose()


def _scene(session_factory) -> tuple[Project, Scene]:
    with session_factory() as session:
        project = Project(
            name="Manual import project",
            description=None,
            aspect_ratio="16:9",
            width=1920,
            height=1080,
            fps=24,
        )
        scene = Scene(
            project_id=project.id,
            scene_number=3,
            title="Scene 03",
            description=None,
            prompt="old prompt",
            negative_prompt="bad",
            seed=None,
            duration_seconds=5,
            megapixels=0.6,
            workflow_template_id=None,
            selected_asset_id=None,
            status="draft",
        )
        session.add(project)
        session.flush()
        scene.project_id = project.id
        session.add(scene)
        session.commit()
        session.refresh(project)
        session.refresh(scene)
        return project, scene


def _upload(
    request,
    scene_id: str,
    filename: str = "manual.mp4",
    content: bytes = b"video-bytes",
    content_type: str = "video/mp4",
    **data: str,
) -> httpx.Response:
    return request(
        "POST",
        f"/api/v1/scenes/{scene_id}/manual-results",
        data or None,
        {"file": (filename, content, content_type)},
    )


def _count(session_factory, model) -> int:
    with session_factory() as session:
        return session.query(model).count()


def _mock_video_metadata(monkeypatch, duration: float = 5.17) -> None:
    monkeypatch.setattr(
        "app.services.manual_result_import.probe_video_metadata",
        lambda _path: VideoMetadata(width=1280, height=720, duration_seconds=duration),
    )
    monkeypatch.setattr(
        "app.services.manual_result_import.generate_video_thumbnail",
        lambda _video_path, output_path, _duration: output_path.write_bytes(b"jpeg"),
    )


def test_manual_video_import_creates_completed_version_with_scene_snapshots(api, monkeypatch) -> None:
    request, session_factory, app_data_dir = api
    project, scene = _scene(session_factory)
    _mock_video_metadata(monkeypatch)

    response = _upload(request, scene.id, seed="123456")

    assert response.status_code == 201
    body = response.json()
    assert body["error"] is None
    job_data = body["data"]
    assert job_data["status"] == "completed"
    assert job_data["workflow_version"] == "manual"
    assert job_data["prompt_snapshot"] == "old prompt"
    assert job_data["negative_prompt_snapshot"] == "bad"
    assert job_data["seed"] == 123456
    assert job_data["params_json"] == {
        "source": "manual_import",
        "source_filename": "manual.mp4",
        "duration_seconds": 5.0,
        "megapixels": 0.6,
    }
    assert len(job_data["outputs"]) == 1
    asset_data = job_data["outputs"][0]["asset"]
    assert asset_data["role"] == "output"
    assert asset_data["type"] == "video"
    assert (asset_data["width"], asset_data["height"], asset_data["duration_seconds"]) == (1280, 720, 5.17)
    assert asset_data["thumbnail_path"] is not None
    assert (app_data_dir / "projects" / project.id / asset_data["relative_path"]).read_bytes() == b"video-bytes"
    assert (app_data_dir / "projects" / project.id / asset_data["thumbnail_path"]).read_bytes() == b"jpeg"

    with session_factory() as session:
        job = session.get(GenerationJob, job_data["id"])
        assert job is not None
        assert job.finished_at is not None
        assert job.comfy_prompt_id is None
        assert job.workflow_template_id
        assert session.query(GenerationOutput).filter_by(generation_job_id=job.id, output_index=0).count() == 1
        workflow = session.get(WorkflowTemplate, job.workflow_template_id)
        assert workflow is not None
        assert workflow.slug == MANUAL_IMPORT_WORKFLOW_SLUG
        assert workflow.is_enabled is False
        persisted_scene = session.get(Scene, scene.id)
        assert persisted_scene is not None
        assert persisted_scene.status == "draft"
        assert persisted_scene.selected_asset_id is None


def test_manual_import_uses_explicit_prompt_and_negative_prompt_snapshots(api) -> None:
    request, session_factory, _ = api
    _project, scene = _scene(session_factory)

    response = _upload(
        request,
        scene.id,
        filename="manual.png",
        content_type="image/png",
        prompt_snapshot="manual prompt",
        negative_prompt_snapshot="manual negative",
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["prompt_snapshot"] == "manual prompt"
    assert data["negative_prompt_snapshot"] == "manual negative"
    assert data["seed"] is None
    assert data["outputs"][0]["asset"]["type"] == "image"
    assert data["outputs"][0]["asset"]["thumbnail_path"] is None
    assert data["outputs"][0]["asset"]["duration_seconds"] is None
    assert _count(session_factory, GenerationJob) == 1


def test_manual_import_can_select_output_as_final_and_existing_select_endpoint_accepts_it(api) -> None:
    request, session_factory, _ = api
    _project, scene = _scene(session_factory)

    response = _upload(
        request,
        scene.id,
        filename="manual.png",
        content_type="image/png",
        select_as_final="true",
    )

    assert response.status_code == 201
    asset_id = response.json()["data"]["outputs"][0]["asset"]["id"]
    with session_factory() as session:
        persisted_scene = session.get(Scene, scene.id)
        assert persisted_scene is not None
        assert persisted_scene.selected_asset_id == asset_id

    selected = request("POST", f"/api/v1/scenes/{scene.id}/assets/{asset_id}/select")
    assert selected.status_code == 200
    assert selected.json()["data"]["selected_asset_id"] == asset_id


def test_manual_import_history_includes_manual_job_and_system_workflow_is_reused_and_hidden(api) -> None:
    request, session_factory, _ = api
    _project, scene = _scene(session_factory)
    with session_factory() as session:
        session.add(
            WorkflowTemplate(
                name="Visible workflow",
                slug="visible-workflow",
                version="1",
                template_path="visible/template.json",
                manifest_path="visible/manifest.json",
                is_enabled=True,
            )
        )
        session.commit()

    first = _upload(request, scene.id, filename="one.png", content_type="image/png")
    second = _upload(request, scene.id, filename="two.png", content_type="image/png")
    assert first.status_code == 201
    assert second.status_code == 201
    assert _count(session_factory, WorkflowTemplate) == 2

    history = request("GET", f"/api/v1/scenes/{scene.id}/generation-jobs")
    assert history.status_code == 200
    assert {job["id"] for job in history.json()["data"]} == {first.json()["data"]["id"], second.json()["data"]["id"]}
    templates = request("GET", "/api/v1/workflow-templates")
    assert templates.status_code == 200
    assert [template["slug"] for template in templates.json()["data"]] == ["visible-workflow"]


def test_manual_import_rejects_unsupported_file_without_rows_or_files(api) -> None:
    request, session_factory, app_data_dir = api
    project, scene = _scene(session_factory)

    response = _upload(request, scene.id, filename="notes.txt", content_type="text/plain", content=b"notes")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MANUAL_RESULT_TYPE_UNSUPPORTED"
    assert _count(session_factory, GenerationJob) == 0
    assert _count(session_factory, Asset) == 0
    assert _count(session_factory, GenerationOutput) == 0
    assert not (app_data_dir / "projects" / project.id).exists()


def test_manual_import_rejects_missing_scene(api) -> None:
    request, session_factory, _ = api

    response = _upload(request, "missing", filename="manual.png", content_type="image/png")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SCENE_NOT_FOUND"
    assert _count(session_factory, GenerationJob) == 0
    assert _count(session_factory, Asset) == 0
    assert _count(session_factory, GenerationOutput) == 0


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (VideoMetadataProbeError("invalid"), 400, "ASSET_MEDIA_INVALID"),
        (FFprobeNotFoundError("missing"), 503, "FFPROBE_NOT_FOUND"),
    ],
)
def test_manual_video_metadata_failure_removes_stored_media(api, monkeypatch, error, status_code, code) -> None:
    request, session_factory, app_data_dir = api
    project, scene = _scene(session_factory)
    monkeypatch.setattr(
        "app.services.manual_result_import.probe_video_metadata",
        lambda _path: (_ for _ in ()).throw(error),
    )

    response = _upload(request, scene.id)

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code
    assert list((app_data_dir / "projects" / project.id / "videos").glob("*")) == []
    assert _count(session_factory, GenerationJob) == 0
    assert _count(session_factory, Asset) == 0
    assert _count(session_factory, GenerationOutput) == 0


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (VideoThumbnailError("failed"), 400, "ASSET_THUMBNAIL_FAILED"),
        (FFmpegNotFoundError("missing"), 503, "FFMPEG_NOT_FOUND"),
    ],
)
def test_manual_video_thumbnail_failure_removes_media_and_thumbnail(api, monkeypatch, error, status_code, code) -> None:
    request, session_factory, app_data_dir = api
    project, scene = _scene(session_factory)
    monkeypatch.setattr(
        "app.services.manual_result_import.probe_video_metadata",
        lambda _path: VideoMetadata(width=1280, height=720, duration_seconds=5.17),
    )

    def fail_thumbnail(_video_path: Path, output_path: Path, _duration: float) -> None:
        output_path.write_bytes(b"partial")
        raise error

    monkeypatch.setattr("app.services.manual_result_import.generate_video_thumbnail", fail_thumbnail)
    response = _upload(request, scene.id)

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code
    assert list((app_data_dir / "projects" / project.id / "videos").glob("*")) == []
    assert list((app_data_dir / "projects" / project.id / "thumbnails").glob("*")) == []
    assert _count(session_factory, GenerationJob) == 0
    assert _count(session_factory, Asset) == 0
    assert _count(session_factory, GenerationOutput) == 0


def test_manual_import_database_failure_rolls_back_and_removes_files(api, monkeypatch) -> None:
    request, session_factory, app_data_dir = api
    project, scene = _scene(session_factory)
    _mock_video_metadata(monkeypatch)

    def fail_commit(_self) -> None:
        raise SQLAlchemyError("commit failed")

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = _upload(request, scene.id)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "MANUAL_RESULT_IMPORT_FAILED"
    assert list((app_data_dir / "projects" / project.id / "videos").glob("*")) == []
    assert list((app_data_dir / "projects" / project.id / "thumbnails").glob("*")) == []
    assert _count(session_factory, GenerationJob) == 0
    assert _count(session_factory, Asset) == 0
    assert _count(session_factory, GenerationOutput) == 0