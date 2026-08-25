import asyncio
from datetime import datetime, timezone
from uuid import UUID

import httpx
import pytest
from sqlalchemy import update

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory, get_db
from app.main import app
from app.models.project import Project


@pytest.fixture
def api(tmp_path):
    database_engine = create_engine_for_path(tmp_path / "projects-api.db")
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
        json: dict | None = None,
    ) -> httpx.Response:
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


def _project_payload(**overrides) -> dict:
    payload = {
        "name": "布布一二故事",
        "description": "项目描述",
        "aspect_ratio": "9:16",
        "width": 1080,
        "height": 1920,
        "fps": 30,
    }
    payload.update(overrides)
    return payload


def _create_project(request, **overrides) -> dict:
    response = request("POST", "/api/v1/projects", _project_payload(**overrides))
    assert response.status_code == 201
    return response.json()["data"]


def test_list_projects_returns_empty_list_then_created_project(api) -> None:
    request, session_factory = api

    empty_response = request("GET", "/api/v1/projects")
    assert empty_response.status_code == 200
    assert empty_response.json() == {"data": [], "error": None}

    created_response = request("POST", "/api/v1/projects", _project_payload())
    assert created_response.status_code == 201
    created_body = created_response.json()
    assert created_body["error"] is None

    created = created_body["data"]
    UUID(created["id"])
    assert created["name"] == "布布一二故事"
    assert created["description"] == "项目描述"
    assert created["aspect_ratio"] == "9:16"
    assert created["width"] == 1080
    assert created["height"] == 1920
    assert created["fps"] == 30
    assert created["created_at"]
    assert created["updated_at"]

    with session_factory() as session:
        persisted = session.get(Project, created["id"])
        assert persisted is not None
        assert persisted.name == "布布一二故事"

    list_response = request("GET", "/api/v1/projects")
    assert list_response.status_code == 200
    assert list_response.json() == {"data": [created], "error": None}


def test_get_project_and_not_found_error(api) -> None:
    request, _ = api
    created = _create_project(request)

    response = request("GET", f"/api/v1/projects/{created['id']}")
    assert response.status_code == 200
    assert response.json() == {"data": created, "error": None}

    missing_response = request("GET", "/api/v1/projects/missing-project")
    assert missing_response.status_code == 404
    assert missing_response.json() == {
        "data": None,
        "error": {
            "code": "PROJECT_NOT_FOUND",
            "message": "Project not found",
        },
    }


def test_patch_project_partially_updates_fields_and_updated_at(api) -> None:
    request, session_factory = api
    created = _create_project(request)
    previous_updated_at = datetime(2000, 1, 1, tzinfo=timezone.utc)

    with session_factory() as session:
        session.execute(
            update(Project)
            .where(Project.id == created["id"])
            .values(updated_at=previous_updated_at)
        )
        session.commit()

    single_field_response = request(
        "PATCH",
        f"/api/v1/projects/{created['id']}",
        {"name": "新项目名称"},
    )
    assert single_field_response.status_code == 200
    single_field = single_field_response.json()
    assert single_field["error"] is None
    assert single_field["data"]["name"] == "新项目名称"
    assert single_field["data"]["description"] == "项目描述"
    assert single_field["data"]["aspect_ratio"] == "9:16"
    assert single_field["data"]["width"] == 1080
    assert single_field["data"]["height"] == 1920
    assert single_field["data"]["fps"] == 30
    assert datetime.fromisoformat(single_field["data"]["updated_at"]) > previous_updated_at

    multi_field_response = request(
        "PATCH",
        f"/api/v1/projects/{created['id']}",
        {
            "description": "更新后的描述",
            "aspect_ratio": "16:9",
            "width": 1920,
            "height": 1080,
            "fps": 24,
        },
    )
    assert multi_field_response.status_code == 200
    multi_field = multi_field_response.json()["data"]
    assert multi_field["name"] == "新项目名称"
    assert multi_field["description"] == "更新后的描述"
    assert multi_field["aspect_ratio"] == "16:9"
    assert multi_field["width"] == 1920
    assert multi_field["height"] == 1080
    assert multi_field["fps"] == 24

    missing_response = request("PATCH", "/api/v1/projects/missing-project", {"name": "x"})
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_delete_project_removes_it_and_returns_not_found_afterward(api) -> None:
    request, _ = api
    created = _create_project(request)

    delete_response = request("DELETE", f"/api/v1/projects/{created['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"data": {"id": created["id"]}, "error": None}

    get_response = request("GET", f"/api/v1/projects/{created['id']}")
    assert get_response.status_code == 404
    assert get_response.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    missing_response = request("DELETE", f"/api/v1/projects/{created['id']}")
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "PROJECT_NOT_FOUND"
