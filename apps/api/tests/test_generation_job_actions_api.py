import asyncio
from uuid import uuid4

import httpx
import pytest

import app.api.generation_jobs as generation_jobs_api
from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory, get_db
from app.main import app
from app.models.generation_job import GenerationJob
from app.models.project import Project
from app.models.scene import Scene
from app.models.workflow_template import WorkflowTemplate


@pytest.fixture
def api(tmp_path):
    engine = create_engine_for_path(tmp_path / "generation-actions-api.db")
    init_db(engine)
    factory = create_session_factory(engine)

    def override():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    def request(path: str) -> httpx.Response:
        async def send() -> httpx.Response:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                return await client.post(path)

        return asyncio.run(send())

    app.dependency_overrides[get_db] = override
    try:
        yield request, factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def _job(factory, status="pending"):
    with factory() as session:
        project = Project(name="API", description=None, aspect_ratio="16:9", width=1, height=1, fps=24)
        session.add(project)
        session.flush()
        scene = Scene(project_id=project.id, scene_number=1, title="Scene", duration_seconds=1)
        workflow = WorkflowTemplate(name="Workflow", slug=f"actions-api-workflow-{uuid4().hex}", version="1", template_path="x", manifest_path="y")
        session.add_all([scene, workflow])
        session.flush()
        job = GenerationJob(project_id=project.id, scene_id=scene.id, workflow_template_id=workflow.id, workflow_version="1", prompt_snapshot="prompt", negative_prompt_snapshot=None, seed=None, params_json={}, status=status)
        session.add(job)
        session.commit()
        return job.id


def test_cancel_api_returns_cancelled_job_and_rejects_terminal_and_missing(api):
    request, factory = api
    pending_id = _job(factory)
    response = request(f"/api/v1/generation-jobs/{pending_id}/cancel")
    assert response.status_code == 200
    assert response.json()["error"] is None
    assert response.json()["data"]["status"] == "cancelled"
    assert response.json()["data"]["finished_at"] is not None

    completed_id = _job(factory, "completed")
    completed = request(f"/api/v1/generation-jobs/{completed_id}/cancel")
    assert completed.status_code == 400
    assert completed.json()["error"]["code"] == "GENERATION_JOB_NOT_CANCELLABLE"

    missing = request("/api/v1/generation-jobs/missing/cancel")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "GENERATION_JOB_NOT_FOUND"


def test_retry_api_returns_new_queued_job(api, monkeypatch):
    request, factory = api
    failed_id = _job(factory, "failed")

    async def retry(db, job_id):
        previous = db.get(GenerationJob, job_id)
        new = GenerationJob(project_id=previous.project_id, scene_id=previous.scene_id, workflow_template_id=previous.workflow_template_id, workflow_version=previous.workflow_version, prompt_snapshot=previous.prompt_snapshot, negative_prompt_snapshot=previous.negative_prompt_snapshot, seed=previous.seed, params_json=previous.params_json, comfy_prompt_id="new-prompt", status="queued")
        db.add(new)
        db.commit()
        db.refresh(new)
        return new

    monkeypatch.setattr(generation_jobs_api, "retry_generation", retry)
    response = request(f"/api/v1/generation-jobs/{failed_id}/retry")
    assert response.status_code == 200
    assert response.json() == {"data": {"job_id": response.json()["data"]["job_id"], "status": "queued"}, "error": None}
    assert response.json()["data"]["job_id"] != failed_id

def test_cancel_not_applied_returns_error_without_broadcast(api, monkeypatch):
    request, _factory = api
    broadcasts = []

    async def not_applied(_db, _job_id):
        raise generation_jobs_api.GenerationServiceError("COMFYUI_CANCEL_NOT_APPLIED", "not applied", 409)

    async def broadcast(event):
        broadcasts.append(event)

    monkeypatch.setattr(generation_jobs_api, "cancel_generation", not_applied)
    monkeypatch.setattr(generation_jobs_api, "broadcast_generation_event", broadcast)
    response = request("/api/v1/generation-jobs/queued-job/cancel")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "COMFYUI_CANCEL_NOT_APPLIED"
    assert broadcasts == []
