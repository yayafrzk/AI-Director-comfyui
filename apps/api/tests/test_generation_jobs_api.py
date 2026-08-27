import asyncio
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory, get_db
from app.main import app
from app.models.generation_job import GenerationJob
from app.models.project import Project
from app.models.scene import Scene
from app.models.workflow_template import WorkflowTemplate


def _get(path):
    async def call():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(path)
    return asyncio.run(call())


def test_generation_history_missing_empty_and_descending(tmp_path):
    engine = create_engine_for_path(tmp_path / "history.db"); init_db(engine); factory = create_session_factory(engine)
    def override():
        session = factory()
        try: yield session
        finally: session.close()
    app.dependency_overrides[get_db] = override
    try:
        assert _get("/api/v1/scenes/missing/generation-jobs").json()["error"]["code"] == "SCENE_NOT_FOUND"
        with factory() as session:
            project = Project(name="History", description=None, aspect_ratio="16:9", width=1, height=1, fps=24); session.add(project); session.commit()
            scene = Scene(project_id=project.id, scene_number=1, title="Scene", description=None, prompt="p", negative_prompt=None, seed=None, duration_seconds=1, workflow_template_id=None, selected_asset_id=None, status="draft")
            workflow = WorkflowTemplate(name="History workflow", slug="history-workflow", version="1", template_path="x", manifest_path="y"); session.add_all([scene, workflow]); session.commit()
            scene_id = scene.id
        assert _get(f"/api/v1/scenes/{scene_id}/generation-jobs").json()["data"] == []
        with factory() as session:
            first = GenerationJob(project_id=project.id, scene_id=scene_id, workflow_template_id=workflow.id, workflow_version="1", prompt_snapshot="p", negative_prompt_snapshot=None, seed=None, params_json={}, created_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
            second = GenerationJob(project_id=project.id, scene_id=scene_id, workflow_template_id=workflow.id, workflow_version="1", prompt_snapshot="p", negative_prompt_snapshot=None, seed=None, params_json={}, created_at=datetime(2025, 1, 2, tzinfo=timezone.utc))
            session.add_all([first, second]); session.commit()
            expected = [second.id, first.id]
        response = _get(f"/api/v1/scenes/{scene_id}/generation-jobs")
        assert response.status_code == 200 and [job["id"] for job in response.json()["data"]] == expected
    finally:
        app.dependency_overrides.pop(get_db, None); engine.dispose()
