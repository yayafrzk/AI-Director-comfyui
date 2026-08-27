import asyncio

import httpx
import pytest
from sqlalchemy import select

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory, get_db
from app.main import app
from app.models.project import Project
from app.models.scene import Scene


@pytest.fixture
def api(tmp_path):
    database_engine = create_engine_for_path(tmp_path / "scenes-reorder-api.db")
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


def _create_scene(request, project_id: str, title: str) -> dict:
    response = request(
        "POST",
        f"/api/v1/projects/{project_id}/scenes",
        {
            "title": title,
            "duration_seconds": 5,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def _numbers_by_title(session_factory, project_id: str) -> dict[str, int]:
    with session_factory() as session:
        scenes = session.scalars(
            select(Scene)
            .where(Scene.project_id == project_id)
            .order_by(Scene.scene_number)
        ).all()
        return {scene.title: scene.scene_number for scene in scenes}


def test_reorder_updates_order_and_get_list(api) -> None:
    request, session_factory = api
    project = _create_project(session_factory, "Reorder project")
    first = _create_scene(request, project.id, "A")
    second = _create_scene(request, project.id, "B")
    third = _create_scene(request, project.id, "C")

    response = request(
        "POST",
        f"/api/v1/projects/{project.id}/scenes/reorder",
        {"scene_ids": [third["id"], first["id"], second["id"]]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert [scene["title"] for scene in body["data"]] == ["C", "A", "B"]
    assert [scene["scene_number"] for scene in body["data"]] == [1, 2, 3]
    assert _numbers_by_title(session_factory, project.id) == {"C": 1, "A": 2, "B": 3}

    list_response = request("GET", f"/api/v1/projects/{project.id}/scenes")
    assert [scene["title"] for scene in list_response.json()["data"]] == ["C", "A", "B"]


def test_reorder_swaps_numbers_without_unique_conflict_and_is_idempotent(api) -> None:
    request, session_factory = api
    project = _create_project(session_factory, "Swap project")
    first = _create_scene(request, project.id, "A")
    second = _create_scene(request, project.id, "B")
    payload = {"scene_ids": [second["id"], first["id"]]}

    first_response = request(
        "POST",
        f"/api/v1/projects/{project.id}/scenes/reorder",
        payload,
    )
    second_response = request(
        "POST",
        f"/api/v1/projects/{project.id}/scenes/reorder",
        payload,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert _numbers_by_title(session_factory, project.id) == {"B": 1, "A": 2}


def test_reorder_after_gap_makes_numbers_contiguous(api) -> None:
    request, session_factory = api
    project = _create_project(session_factory, "Gap project")
    first = _create_scene(request, project.id, "A")
    second = _create_scene(request, project.id, "B")
    third = _create_scene(request, project.id, "C")
    fourth = _create_scene(request, project.id, "D")

    assert request("DELETE", f"/api/v1/scenes/{second['id']}").status_code == 200
    response = request(
        "POST",
        f"/api/v1/projects/{project.id}/scenes/reorder",
        {"scene_ids": [fourth["id"], first["id"], third["id"]]},
    )

    assert response.status_code == 200
    assert _numbers_by_title(session_factory, project.id) == {"D": 1, "A": 2, "C": 3}


def test_reorder_rejects_invalid_complete_orders_without_mutation(api) -> None:
    request, session_factory = api
    first_project = _create_project(session_factory, "First")
    second_project = _create_project(session_factory, "Second")
    first = _create_scene(request, first_project.id, "A")
    second = _create_scene(request, first_project.id, "B")
    other = _create_scene(request, second_project.id, "Other")
    original_first = _numbers_by_title(session_factory, first_project.id)
    original_second = _numbers_by_title(session_factory, second_project.id)

    invalid_orders = [
        [first["id"]],
        [first["id"], second["id"], "missing-scene"],
        [first["id"], first["id"]],
        [first["id"], other["id"]],
    ]
    for scene_ids in invalid_orders:
        response = request(
            "POST",
            f"/api/v1/projects/{first_project.id}/scenes/reorder",
            {"scene_ids": scene_ids},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "SCENE_REORDER_INVALID"
        assert _numbers_by_title(session_factory, first_project.id) == original_first
        assert _numbers_by_title(session_factory, second_project.id) == original_second


def test_reorder_handles_missing_project_and_empty_project(api) -> None:
    request, session_factory = api
    missing_response = request(
        "POST",
        "/api/v1/projects/missing-project/scenes/reorder",
        {"scene_ids": []},
    )
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    project = _create_project(session_factory, "Empty")
    empty_response = request(
        "POST",
        f"/api/v1/projects/{project.id}/scenes/reorder",
        {"scene_ids": []},
    )
    assert empty_response.status_code == 200
    assert empty_response.json() == {"data": [], "error": None}
