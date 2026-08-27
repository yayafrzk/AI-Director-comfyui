import asyncio
from uuid import UUID

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
    database_engine = create_engine_for_path(tmp_path / "scenes-create-api.db")
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
        "title": "公园出发",
        "description": "一二和布布准备出发",
        "prompt": "two bears at a park entrance",
        "negative_prompt": "blurry",
        "seed": 123456,
        "duration_seconds": 5,
        "workflow_template_id": None,
    }
    payload.update(overrides)
    return payload


def test_create_scene_returns_project_not_found(api) -> None:
    request, _ = api

    response = request("POST", "/api/v1/projects/not-exist/scenes", _scene_payload())

    assert response.status_code == 404
    assert response.json() == {
        "data": None,
        "error": {
            "code": "PROJECT_NOT_FOUND",
            "message": "Project not found",
        },
    }


def test_create_first_scene_returns_and_persists_full_data(api) -> None:
    request, session_factory = api
    project = _create_project(session_factory, "Scene project")

    response = request("POST", f"/api/v1/projects/{project.id}/scenes", _scene_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["error"] is None
    scene = body["data"]
    UUID(scene["id"])
    assert scene["project_id"] == project.id
    assert scene["scene_number"] == 1
    assert scene["title"] == "公园出发"
    assert scene["description"] == "一二和布布准备出发"
    assert scene["prompt"] == "two bears at a park entrance"
    assert scene["negative_prompt"] == "blurry"
    assert scene["seed"] == 123456
    assert scene["duration_seconds"] == 5
    assert scene["workflow_template_id"] is None
    assert scene["selected_asset_id"] is None
    assert scene["status"] == "draft"
    assert scene["created_at"]
    assert scene["updated_at"]

    with session_factory() as session:
        persisted = session.get(Scene, scene["id"])
        assert persisted is not None
        assert persisted.project_id == project.id
        assert persisted.scene_number == 1


def test_scene_numbers_are_sequential_per_project_and_allow_null_fields(api) -> None:
    request, session_factory = api
    first_project = _create_project(session_factory, "First")
    second_project = _create_project(session_factory, "Second")

    first_numbers = [
        request(
            "POST",
            f"/api/v1/projects/{first_project.id}/scenes",
            _scene_payload(title=f"Scene {index}"),
        ).json()["data"]["scene_number"]
        for index in range(1, 4)
    ]
    second_number = request(
        "POST",
        f"/api/v1/projects/{second_project.id}/scenes",
        _scene_payload(
            title="Nullable scene",
            description=None,
            prompt=None,
            negative_prompt=None,
            seed=None,
            workflow_template_id=None,
        ),
    ).json()["data"]["scene_number"]

    assert first_numbers == [1, 2, 3]
    assert second_number == 1


def test_scene_number_uses_maximum_instead_of_count(api) -> None:
    request, session_factory = api
    project = _create_project(session_factory, "Gap project")

    with session_factory() as session:
        session.add_all(
            [
                Scene(
                    project_id=project.id,
                    scene_number=1,
                    title="First",
                    duration_seconds=5,
                ),
                Scene(
                    project_id=project.id,
                    scene_number=3,
                    title="Third",
                    duration_seconds=5,
                ),
            ]
        )
        session.commit()

    response = request("POST", f"/api/v1/projects/{project.id}/scenes", _scene_payload())

    assert response.status_code == 201
    assert response.json()["data"]["scene_number"] == 4
    with session_factory() as session:
        assert session.scalars(select(Scene).where(Scene.project_id == project.id)).all()
