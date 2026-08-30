import asyncio

import httpx
import pytest

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory, get_db
from app.main import app
from app.models.asset import Asset
from app.models.generation_job import GenerationJob
from app.models.generation_output import GenerationOutput
from app.models.project import Project
from app.models.scene import Scene
from app.models.workflow_template import WorkflowTemplate


@pytest.fixture
def api(tmp_path):
    engine = create_engine_for_path(tmp_path / "selected-asset.db")
    init_db(engine)
    session_factory = create_session_factory(engine)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def request(method: str, path: str) -> httpx.Response:
        async def send() -> httpx.Response:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                return await client.request(method, path)

        return asyncio.run(send())

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield request, session_factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def _scene(session, project_id: str, scene_number: int) -> Scene:
    scene = Scene(
        project_id=project_id,
        scene_number=scene_number,
        title=f"Scene {scene_number}",
        duration_seconds=1,
    )
    session.add(scene)
    session.flush()
    return scene


def _generation_asset(session, project_id: str, scene: Scene, workflow_id: str, name: str) -> Asset:
    job = GenerationJob(
        project_id=project_id,
        scene_id=scene.id,
        workflow_template_id=workflow_id,
        workflow_version="1",
        prompt_snapshot="prompt",
        negative_prompt_snapshot=None,
        seed=None,
        params_json={},
        status="completed",
    )
    asset = Asset(
        project_id=project_id,
        scene_id=scene.id,
        type="video",
        role="output",
        relative_path=f"videos/{name}.mp4",
        thumbnail_path=None,
        mime_type="video/mp4",
        width=None,
        height=None,
        duration_seconds=None,
        size_bytes=1,
        hash=None,
    )
    session.add_all([job, asset])
    session.flush()
    session.add(GenerationOutput(generation_job_id=job.id, asset_id=asset.id, output_index=0))
    session.flush()
    return asset


def _fixture_data(session_factory):
    with session_factory() as session:
        project = Project(name="Selected asset", description=None, aspect_ratio="16:9", width=1, height=1, fps=24)
        session.add(project)
        session.flush()
        first_scene = _scene(session, project.id, 1)
        second_scene = _scene(session, project.id, 2)
        workflow = WorkflowTemplate(name="Workflow", slug="select-workflow", version="1", template_path="x", manifest_path="y")
        session.add(workflow)
        session.flush()
        first_asset = _generation_asset(session, project.id, first_scene, workflow.id, "first")
        second_asset = _generation_asset(session, project.id, first_scene, workflow.id, "second")
        other_scene_asset = _generation_asset(session, project.id, second_scene, workflow.id, "other")
        reference_asset = Asset(project_id=project.id, scene_id=first_scene.id, type="image", role="reference", relative_path="images/reference.png", thumbnail_path=None, mime_type="image/png", width=None, height=None, duration_seconds=None, size_bytes=1, hash=None)
        orphan_output_asset = Asset(project_id=project.id, scene_id=first_scene.id, type="image", role="output", relative_path="images/orphan.png", thumbnail_path=None, mime_type="image/png", width=None, height=None, duration_seconds=None, size_bytes=1, hash=None)
        session.add_all([reference_asset, orphan_output_asset])
        session.commit()
        return first_scene.id, second_scene.id, first_asset.id, second_asset.id, other_scene_asset.id, reference_asset.id, orphan_output_asset.id


def test_select_generation_output_persists_switches_and_is_idempotent(api) -> None:
    request, session_factory = api
    scene_id, _other_scene_id, first_asset_id, second_asset_id, *_ = _fixture_data(session_factory)

    first = request("POST", f"/api/v1/scenes/{scene_id}/assets/{first_asset_id}/select")
    assert first.status_code == 200
    assert set(first.json()) == {"data", "error"}
    assert first.json()["error"] is None
    assert first.json()["data"]["selected_asset_id"] == first_asset_id

    repeated = request("POST", f"/api/v1/scenes/{scene_id}/assets/{first_asset_id}/select")
    assert repeated.status_code == 200
    assert repeated.json()["data"]["selected_asset_id"] == first_asset_id

    switched = request("POST", f"/api/v1/scenes/{scene_id}/assets/{second_asset_id}/select")
    assert switched.status_code == 200
    assert switched.json()["data"]["selected_asset_id"] == second_asset_id

    refreshed = request("GET", f"/api/v1/scenes/{scene_id}")
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["selected_asset_id"] == second_asset_id


def test_select_generation_output_rejects_invalid_scene_and_assets(api) -> None:
    request, session_factory = api
    scene_id, _other_scene_id, first_asset_id, _second_asset_id, other_scene_asset_id, reference_asset_id, orphan_output_asset_id = _fixture_data(session_factory)

    missing_scene = request("POST", f"/api/v1/scenes/missing/assets/{first_asset_id}/select")
    assert missing_scene.status_code == 404
    assert missing_scene.json()["error"]["code"] == "SCENE_NOT_FOUND"

    missing_asset = request("POST", f"/api/v1/scenes/{scene_id}/assets/missing/select")
    assert missing_asset.status_code == 404
    assert missing_asset.json()["error"]["code"] == "ASSET_NOT_FOUND"

    other_scene = request("POST", f"/api/v1/scenes/{scene_id}/assets/{other_scene_asset_id}/select")
    assert other_scene.status_code == 400
    assert other_scene.json()["error"]["code"] == "ASSET_NOT_IN_SCENE"

    reference = request("POST", f"/api/v1/scenes/{scene_id}/assets/{reference_asset_id}/select")
    assert reference.status_code == 400
    assert reference.json()["error"]["code"] == "ASSET_NOT_GENERATION_OUTPUT"

    orphan = request("POST", f"/api/v1/scenes/{scene_id}/assets/{orphan_output_asset_id}/select")
    assert orphan.status_code == 400
    assert orphan.json()["error"]["code"] == "ASSET_NOT_GENERATION_OUTPUT"

    with session_factory() as session:
        scene = session.get(Scene, scene_id)
        assert scene is not None
        assert scene.selected_asset_id is None
