import asyncio
from datetime import datetime, timezone

import httpx

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory, get_db
from app.main import app
from app.models.asset import Asset
from app.models.generation_job import GenerationJob
from app.models.generation_output import GenerationOutput
from app.models.project import Project
from app.models.scene import Scene
from app.models.workflow_template import WorkflowTemplate


def _get(path: str) -> httpx.Response:
    async def call() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.get(path)

    return asyncio.run(call())


def test_generation_history_missing_empty_and_descending(tmp_path):
    engine = create_engine_for_path(tmp_path / "history.db")
    init_db(engine)
    factory = create_session_factory(engine)

    def override():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override
    try:
        assert _get("/api/v1/scenes/missing/generation-jobs").json()["error"]["code"] == "SCENE_NOT_FOUND"
        with factory() as session:
            project = Project(name="History", description=None, aspect_ratio="16:9", width=1, height=1, fps=24)
            session.add(project)
            session.flush()
            scene = Scene(project_id=project.id, scene_number=1, title="Scene", description=None, prompt="p", negative_prompt=None, seed=None, duration_seconds=1, workflow_template_id=None, selected_asset_id=None, status="draft")
            workflow = WorkflowTemplate(name="History workflow", slug="history-workflow", version="1", template_path="x", manifest_path="y")
            session.add_all([scene, workflow])
            session.commit()
            scene_id = scene.id

        assert _get(f"/api/v1/scenes/{scene_id}/generation-jobs").json()["data"] == []

        with factory() as session:
            first = GenerationJob(project_id=project.id, scene_id=scene_id, workflow_template_id=workflow.id, workflow_version="1", prompt_snapshot="p", negative_prompt_snapshot=None, seed=None, params_json={}, created_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
            second = GenerationJob(project_id=project.id, scene_id=scene_id, workflow_template_id=workflow.id, workflow_version="1", prompt_snapshot="p", negative_prompt_snapshot=None, seed=None, params_json={}, created_at=datetime(2025, 1, 2, tzinfo=timezone.utc))
            session.add_all([first, second])
            session.commit()
            expected = [second.id, first.id]

        response = _get(f"/api/v1/scenes/{scene_id}/generation-jobs")
        assert response.status_code == 200
        assert [job["id"] for job in response.json()["data"]] == expected
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_generation_history_includes_outputs_in_stable_output_order(tmp_path):
    engine = create_engine_for_path(tmp_path / "history_outputs.db")
    init_db(engine)
    factory = create_session_factory(engine)

    def override():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override
    try:
        with factory() as session:
            project = Project(name="History", description=None, aspect_ratio="16:9", width=1, height=1, fps=24)
            session.add(project)
            session.flush()
            scene = Scene(project_id=project.id, scene_number=1, title="Scene", description=None, prompt="p", negative_prompt=None, seed=None, duration_seconds=1, workflow_template_id=None, selected_asset_id=None, status="draft")
            workflow = WorkflowTemplate(name="History workflow", slug="history-outputs-workflow", version="1", template_path="x", manifest_path="y")
            session.add_all([scene, workflow])
            session.flush()
            completed_job = GenerationJob(project_id=project.id, scene_id=scene.id, workflow_template_id=workflow.id, workflow_version="1", prompt_snapshot="p", negative_prompt_snapshot=None, seed=None, params_json={}, status="completed", created_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
            failed_job = GenerationJob(project_id=project.id, scene_id=scene.id, workflow_template_id=workflow.id, workflow_version="1", prompt_snapshot="p", negative_prompt_snapshot=None, seed=None, params_json={}, status="failed", created_at=datetime(2025, 1, 2, tzinfo=timezone.utc))
            session.add_all([completed_job, failed_job])
            session.flush()
            first_asset = Asset(project_id=project.id, scene_id=scene.id, type="image", role="output", relative_path="images/first.png", thumbnail_path=None, mime_type="image/png", width=640, height=360, duration_seconds=None, size_bytes=10, hash=None)
            second_asset = Asset(project_id=project.id, scene_id=scene.id, type="video", role="output", relative_path="videos/second.mp4", thumbnail_path=None, mime_type="video/mp4", width=None, height=None, duration_seconds=None, size_bytes=20, hash=None)
            session.add_all([first_asset, second_asset])
            session.flush()
            session.add_all([
                GenerationOutput(generation_job_id=completed_job.id, asset_id=second_asset.id, output_index=1),
                GenerationOutput(generation_job_id=completed_job.id, asset_id=first_asset.id, output_index=0),
            ])
            session.commit()
            scene_id = scene.id
            completed_job_id = completed_job.id
            failed_job_id = failed_job.id

        response = _get(f"/api/v1/scenes/{scene_id}/generation-jobs")
        assert response.status_code == 200
        jobs = response.json()["data"]
        assert [job["id"] for job in jobs] == [failed_job_id, completed_job_id]
        assert jobs[0]["outputs"] == []
        outputs = jobs[1]["outputs"]
        assert [output["output_index"] for output in outputs] == [0, 1]
        assert [output["asset"]["relative_path"] for output in outputs] == ["images/first.png", "videos/second.mp4"]
        assert outputs[0]["asset"]["mime_type"] == "image/png"
        assert outputs[1]["asset"]["mime_type"] == "video/mp4"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
