import asyncio
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import select, update

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory, get_db
from app.main import app
from app.models.project import Project
from app.models.scene import Scene


@pytest.fixture
def api(tmp_path):
    database_engine = create_engine_for_path(tmp_path / "scenes-api.db")
    init_db(database_engine)
    session_factory = create_session_factory(database_engine)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def request(method: str, path: str, json: dict | None = None) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.request(method, path, json=json)

        return asyncio.run(send())

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield request, session_factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        database_engine.dispose()


def _create_project(session_factory, name: str) -> Project:
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


def _scene_payload(**overrides) -> dict:
    payload = {
        "title": "Scene title",
        "description": "Scene description",
        "prompt": "Scene prompt",
        "negative_prompt": "Scene negative prompt",
        "seed": 123456,
        "duration_seconds": 5,
        "workflow_template_id": "workflow-id",
    }
    payload.update(overrides)
    return payload


def _create_scene(request, project_id: str, **overrides) -> dict:
    response = request(
        "POST",
        f"/api/v1/projects/{project_id}/scenes",
        _scene_payload(**overrides),
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_list_project_scenes_handles_empty_and_missing_project(api) -> None:
    request, session_factory = api
    project = _create_project(session_factory, "Empty project")

    empty_response = request("GET", f"/api/v1/projects/{project.id}/scenes")
    assert empty_response.status_code == 200
    assert empty_response.json() == {"data": [], "error": None}

    missing_response = request("GET", "/api/v1/projects/missing-project/scenes")
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_list_project_scenes_is_sorted_and_isolated(api) -> None:
    request, session_factory = api
    first_project = _create_project(session_factory, "First")
    second_project = _create_project(session_factory, "Second")

    with session_factory() as session:
        session.add_all(
            [
                Scene(
                    project_id=first_project.id,
                    scene_number=3,
                    title="Third",
                    duration_seconds=5,
                ),
                Scene(
                    project_id=first_project.id,
                    scene_number=1,
                    title="First",
                    duration_seconds=5,
                ),
                Scene(
                    project_id=first_project.id,
                    scene_number=2,
                    title="Second",
                    duration_seconds=5,
                ),
                Scene(
                    project_id=second_project.id,
                    scene_number=1,
                    title="Other project",
                    duration_seconds=5,
                ),
            ]
        )
        session.commit()

    response = request("GET", f"/api/v1/projects/{first_project.id}/scenes")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert [scene["scene_number"] for scene in body["data"]] == [1, 2, 3]
    assert {scene["project_id"] for scene in body["data"]} == {first_project.id}


def test_get_and_patch_scene_support_partial_and_null_updates(api) -> None:
    request, session_factory = api
    project = _create_project(session_factory, "Patch project")
    scene = _create_scene(request, project.id)

    detail_response = request("GET", f"/api/v1/scenes/{scene['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json() == {"data": scene, "error": None}

    old_updated_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    with session_factory() as session:
        session.execute(
            update(Scene)
            .where(Scene.id == scene["id"])
            .values(updated_at=old_updated_at)
        )
        session.commit()

    single_response = request(
        "PATCH",
        f"/api/v1/scenes/{scene['id']}",
        {"title": "Renamed scene", "scene_number": 99},
    )
    assert single_response.status_code == 200
    single = single_response.json()["data"]
    assert single["title"] == "Renamed scene"
    assert single["scene_number"] == 1
    assert single["description"] == "Scene description"
    assert single["seed"] == 123456
    assert datetime.fromisoformat(single["updated_at"]) > old_updated_at

    multi_response = request(
        "PATCH",
        f"/api/v1/scenes/{scene['id']}",
        {
            "prompt": "Updated prompt",
            "duration_seconds": 8,
            "status": "ready",
        },
    )
    assert multi_response.status_code == 200
    multi = multi_response.json()["data"]
    assert multi["title"] == "Renamed scene"
    assert multi["prompt"] == "Updated prompt"
    assert multi["duration_seconds"] == 8
    assert multi["status"] == "ready"
    assert multi["negative_prompt"] == "Scene negative prompt"

    null_response = request(
        "PATCH",
        f"/api/v1/scenes/{scene['id']}",
        {
            "description": None,
            "prompt": None,
            "negative_prompt": None,
            "seed": None,
            "workflow_template_id": None,
        },
    )
    assert null_response.status_code == 200
    nullable = null_response.json()["data"]
    assert nullable["description"] is None
    assert nullable["prompt"] is None
    assert nullable["negative_prompt"] is None
    assert nullable["seed"] is None
    assert nullable["workflow_template_id"] is None

    with session_factory() as session:
        persisted = session.get(Scene, scene["id"])
        assert persisted is not None
        assert persisted.scene_number == 1
        assert persisted.seed is None

    missing_response = request("PATCH", "/api/v1/scenes/missing-scene", {"title": "x"})
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "SCENE_NOT_FOUND"


def test_delete_scene_does_not_reorder_and_create_continues_from_maximum(api) -> None:
    request, session_factory = api
    project = _create_project(session_factory, "Delete project")
    first = _create_scene(request, project.id, title="First")
    second = _create_scene(request, project.id, title="Second")
    third = _create_scene(request, project.id, title="Third")

    delete_response = request("DELETE", f"/api/v1/scenes/{second['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"data": {"id": second["id"]}, "error": None}

    with session_factory() as session:
        remaining_numbers = session.scalars(
            select(Scene.scene_number)
            .where(Scene.project_id == project.id)
            .order_by(Scene.scene_number)
        ).all()
        assert remaining_numbers == [1, 3]

    get_response = request("GET", f"/api/v1/scenes/{second['id']}")
    assert get_response.status_code == 404
    assert get_response.json()["error"]["code"] == "SCENE_NOT_FOUND"

    missing_delete = request("DELETE", f"/api/v1/scenes/{second['id']}")
    assert missing_delete.status_code == 404
    assert missing_delete.json()["error"]["code"] == "SCENE_NOT_FOUND"

    created_after_delete = _create_scene(request, project.id, title="Fourth")
    assert created_after_delete["scene_number"] == 4
    assert first["scene_number"] == 1
    assert third["scene_number"] == 3
