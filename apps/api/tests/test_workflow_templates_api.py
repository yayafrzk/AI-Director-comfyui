import asyncio
import json
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory, get_db
from app.main import app
from app.models.workflow_template import WorkflowTemplate
from app.services.workflow_loader import load_workflow_template


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKFLOWS_DIR", str(tmp_path / "workflows"))
    engine = create_engine_for_path(tmp_path / "api.db")
    init_db(engine)
    session_factory = create_session_factory(engine)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def request(method: str, path: str, body: dict | None = None) -> httpx.Response:
        async def send() -> httpx.Response:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                return await client.request(method, path, json=body)

        return asyncio.run(send())

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield request, session_factory, tmp_path / "workflows"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def import_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Demo workflow",
        "slug": "demo",
        "version": "1.0.0",
        "template_path": "demo/template.json",
        "manifest_path": "demo/manifest.json",
        "is_enabled": True,
    }
    payload.update(overrides)
    return payload


def write_workflow(root, manifest: object | None = None) -> None:
    directory = root / "demo"
    directory.mkdir(parents=True)
    (directory / "template.json").write_text(json.dumps({"1": {}}), encoding="utf-8")
    (directory / "manifest.json").write_text(
        json.dumps(manifest or {"id": "demo", "name": "Demo", "version": "1.0.0", "inputs": {}}),
        encoding="utf-8",
    )


def template(slug: str, identifier: str, created_at: datetime, is_enabled: bool = True) -> WorkflowTemplate:
    return WorkflowTemplate(
        id=identifier,
        name=slug,
        slug=slug,
        version="1.0.0",
        template_path="demo/template.json",
        manifest_path="demo/manifest.json",
        is_enabled=is_enabled,
        created_at=created_at,
        updated_at=created_at,
    )


def workflow_count(session_factory) -> int:
    with session_factory() as session:
        return session.query(WorkflowTemplate).count()


def test_list_orders_by_created_at_then_id_and_includes_disabled(api) -> None:
    request, session_factory, _ = api
    first_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    second_time = datetime(2024, 1, 2, tzinfo=timezone.utc)
    with session_factory() as session:
        session.add_all([
            template("late", "c-id", second_time),
            template("same-high", "b-id", first_time, is_enabled=False),
            template("same-low", "a-id", first_time),
        ])
        session.commit()

    response = request("GET", "/api/v1/workflow-templates")

    assert response.status_code == 200
    data = response.json()["data"]
    assert [item["id"] for item in data] == ["a-id", "b-id", "c-id"]
    assert data[1]["is_enabled"] is False


def test_valid_import_persists_response_metadata_and_reloads(api) -> None:
    request, session_factory, workflow_root = api
    write_workflow(workflow_root)

    response = request("POST", "/api/v1/workflow-templates/import", import_payload(name="Display name", is_enabled=False))

    assert response.status_code == 201
    data = response.json()["data"]
    assert {key: data[key] for key in ("name", "slug", "version", "template_path", "manifest_path", "is_enabled")} == {
        "name": "Display name", "slug": "demo", "version": "1.0.0",
        "template_path": "demo/template.json", "manifest_path": "demo/manifest.json", "is_enabled": False,
    }
    with session_factory() as session:
        row = session.get(WorkflowTemplate, data["id"])
        assert row is not None
        assert load_workflow_template(row).manifest.id == "demo"


def test_manifest_invalid_json_returns_400_without_row(api) -> None:
    request, session_factory, workflow_root = api
    write_workflow(workflow_root)
    (workflow_root / "demo" / "manifest.json").write_text("{invalid", encoding="utf-8")

    response = request("POST", "/api/v1/workflow-templates/import", import_payload())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WORKFLOW_JSON_INVALID"
    assert workflow_count(session_factory) == 0


def test_manifest_version_mismatch_returns_400_without_row(api) -> None:
    request, session_factory, workflow_root = api
    write_workflow(workflow_root, {"id": "demo", "name": "Demo", "version": "2.0.0", "inputs": {}})

    response = request("POST", "/api/v1/workflow-templates/import", import_payload(version="1.0.0"))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WORKFLOW_MANIFEST_MISMATCH"
    assert workflow_count(session_factory) == 0


def test_commit_sqlalchemy_error_returns_500_and_rolls_back(api, monkeypatch) -> None:
    request, session_factory, workflow_root = api
    write_workflow(workflow_root)

    monkeypatch.setattr(Session, "commit", lambda _self: (_ for _ in ()).throw(SQLAlchemyError("database failed")))
    response = request("POST", "/api/v1/workflow-templates/import", import_payload())

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "WORKFLOW_TEMPLATE_IMPORT_FAILED"
    assert workflow_count(session_factory) == 0


def test_non_slug_integrity_error_returns_500_and_rolls_back(api, monkeypatch) -> None:
    request, session_factory, workflow_root = api
    write_workflow(workflow_root)

    monkeypatch.setattr(Session, "commit", lambda _self: (_ for _ in ()).throw(IntegrityError("statement", {}, Exception("other constraint"))))
    response = request("POST", "/api/v1/workflow-templates/import", import_payload())

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "WORKFLOW_TEMPLATE_IMPORT_FAILED"
    assert workflow_count(session_factory) == 0

def test_empty_workflow_template_list_returns_empty_envelope(api) -> None:
    request, _, _ = api

    response = request("GET", "/api/v1/workflow-templates")

    assert response.status_code == 200
    assert response.json() == {"data": [], "error": None}


def test_workflow_template_detail_returns_existing_template(api) -> None:
    request, session_factory, _ = api
    created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    with session_factory() as session:
        row = template("detail-slug", "detail-id", created_at)
        session.add(row)
        session.commit()

    response = request("GET", "/api/v1/workflow-templates/detail-id")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == "detail-id"
    assert response.json()["data"]["slug"] == "detail-slug"
    assert response.json()["data"]["version"] == "1.0.0"


def test_workflow_template_detail_missing_returns_not_found(api) -> None:
    request, _, _ = api

    response = request("GET", "/api/v1/workflow-templates/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WORKFLOW_TEMPLATE_NOT_FOUND"


def test_duplicate_slug_import_does_not_upsert(api) -> None:
    request, session_factory, workflow_root = api
    write_workflow(workflow_root)

    first = request("POST", "/api/v1/workflow-templates/import", import_payload(name="First"))
    second = request("POST", "/api/v1/workflow-templates/import", import_payload(name="Second"))

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "WORKFLOW_TEMPLATE_SLUG_EXISTS"
    assert workflow_count(session_factory) == 1
    with session_factory() as session:
        row = session.query(WorkflowTemplate).one()
        assert row.name == "First"


@pytest.mark.parametrize("unsafe_path", ["../x", "/x", "C:\\x"])
def test_import_rejects_path_escape_without_row(api, unsafe_path: str) -> None:
    request, session_factory, workflow_root = api
    write_workflow(workflow_root)

    response = request("POST", "/api/v1/workflow-templates/import", import_payload(template_path=unsafe_path))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WORKFLOW_PATH_INVALID"
    assert workflow_count(session_factory) == 0


def test_import_missing_workflow_files_returns_not_found_without_row(api) -> None:
    request, session_factory, workflow_root = api
    workflow_root.mkdir(parents=True)

    response = request("POST", "/api/v1/workflow-templates/import", import_payload())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WORKFLOW_FILE_NOT_FOUND"
    assert workflow_count(session_factory) == 0


def test_template_invalid_json_returns_400_without_row(api) -> None:
    request, session_factory, workflow_root = api
    write_workflow(workflow_root)
    (workflow_root / "demo" / "template.json").write_text("{invalid", encoding="utf-8")

    response = request("POST", "/api/v1/workflow-templates/import", import_payload())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WORKFLOW_JSON_INVALID"
    assert workflow_count(session_factory) == 0


def test_template_root_non_object_returns_400_without_row(api) -> None:
    request, session_factory, workflow_root = api
    write_workflow(workflow_root)
    (workflow_root / "demo" / "template.json").write_text("[]", encoding="utf-8")

    response = request("POST", "/api/v1/workflow-templates/import", import_payload())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WORKFLOW_TEMPLATE_INVALID"
    assert workflow_count(session_factory) == 0


def test_manifest_schema_invalid_returns_400_without_row(api) -> None:
    request, session_factory, workflow_root = api
    write_workflow(workflow_root, {"id": "demo"})

    response = request("POST", "/api/v1/workflow-templates/import", import_payload())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WORKFLOW_MANIFEST_INVALID"
    assert workflow_count(session_factory) == 0


def test_manifest_slug_mismatch_returns_400_without_row(api) -> None:
    request, session_factory, workflow_root = api
    write_workflow(workflow_root, {"id": "other", "name": "Demo", "version": "1.0.0", "inputs": {}})

    response = request("POST", "/api/v1/workflow-templates/import", import_payload(slug="demo"))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WORKFLOW_MANIFEST_MISMATCH"
    assert workflow_count(session_factory) == 0