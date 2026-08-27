import asyncio

import httpx
import pytest
from sqlalchemy import select

import app.services.generation_service as generation_service
from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory, get_db
from app.main import app
from app.models.generation_job import GenerationJob
from app.models.project import Project
from app.models.scene import Scene
from app.models.workflow_template import WorkflowTemplate
from app.schemas.workflow_manifest import WorkflowManifest
from app.services.comfyui_client import ComfyUIClientError
from app.services.workflow_loader import LoadedWorkflowTemplate, WorkflowLoadError


@pytest.fixture
def api(tmp_path):
    engine = create_engine_for_path(tmp_path / "api.db"); init_db(engine); factory = create_session_factory(engine)
    def override():
        session = factory()
        try: yield session
        finally: session.close()
    app.dependency_overrides[get_db] = override
    try: yield factory
    finally: app.dependency_overrides.pop(get_db, None); engine.dispose()


def _deps(factory, enabled=True):
    with factory() as s:
        p=Project(name="p",description=None,aspect_ratio="16:9",width=1,height=1,fps=24); s.add(p); s.commit()
        scene=Scene(project_id=p.id,scene_number=1,title="s",description=None,prompt="prompt",negative_prompt="negative",seed=11,duration_seconds=1,workflow_template_id=None,selected_asset_id=None,status="draft")
        workflow=WorkflowTemplate(name="w",slug="w",version="1",template_path="x",manifest_path="y",is_enabled=enabled); s.add_all([scene,workflow]); s.commit(); return scene,workflow


def _post(path, body):
    async def call():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as c: return await c.post(path,json=body)
    return asyncio.run(call())


def _mock_success(monkeypatch):
    manifest=WorkflowManifest.model_validate({"id":"w","name":"w","version":"1","inputs":{"prompt":{"node_id":"1","field":"text","required":True},"seed":{"node_id":"1","field":"text"}}})
    monkeypatch.setattr(generation_service,"load_workflow_template",lambda _: LoadedWorkflowTemplate({"1":{"inputs":{"text":""}}},manifest))
    monkeypatch.setattr(generation_service,"build_workflow",lambda *_: {"built":True})
    async def submit(_, client_id=None):
        assert client_id
        return "prompt-123"
    monkeypatch.setattr(generation_service,"submit_prompt",submit)


def test_generate_route_success_and_no_scene_mutation(api, monkeypatch):
    scene,workflow=_deps(api); _mock_success(monkeypatch)
    response=_post(f"/api/v1/scenes/{scene.id}/generate",{"workflow_template_id":workflow.id,"seed":22,"params":{"cfg":5}})
    assert response.status_code==200 and response.json()["error"] is None
    assert set(response.json()["data"])=={"job_id","status"} and response.json()["data"]["status"]=="queued"
    with api() as s:
        job=s.get(GenerationJob,response.json()["data"]["job_id"]); current=s.get(Scene,scene.id)
        assert job.status=="queued" and job.comfy_prompt_id=="prompt-123" and job.seed==22
        assert (current.status,current.prompt,current.seed)==("draft","prompt",11)


@pytest.mark.parametrize("key",["seed","prompt","negative_prompt"])
def test_generate_route_rejects_reserved_params_without_job(api,key):
    scene,workflow=_deps(api); response=_post(f"/api/v1/scenes/{scene.id}/generate",{"workflow_template_id":workflow.id,"params":{key:1}})
    assert response.status_code==400 and response.json()["error"]["code"]=="GENERATION_PARAMS_INVALID"
    with api() as s: assert s.scalars(select(GenerationJob)).all()==[]


def test_generate_route_missing_scene_workflow_disabled_and_bool_seed(api):
    scene,disabled=_deps(api,False)
    assert _post("/api/v1/scenes/missing/generate",{"workflow_template_id":disabled.id}).json()["error"]["code"]=="SCENE_NOT_FOUND"
    assert _post(f"/api/v1/scenes/{scene.id}/generate",{"workflow_template_id":"missing"}).json()["error"]["code"]=="WORKFLOW_TEMPLATE_NOT_FOUND"
    assert _post(f"/api/v1/scenes/{scene.id}/generate",{"workflow_template_id":disabled.id}).json()["error"]["code"]=="WORKFLOW_TEMPLATE_DISABLED"
    assert _post(f"/api/v1/scenes/{scene.id}/generate",{"workflow_template_id":disabled.id,"seed":True}).status_code==422


@pytest.mark.parametrize("error,code,status",[(WorkflowLoadError("WORKFLOW_MANIFEST_MISMATCH","bad"),"WORKFLOW_MANIFEST_MISMATCH",400),(ComfyUIClientError("COMFYUI_OFFLINE","off"),"COMFYUI_OFFLINE",503),(ComfyUIClientError("COMFYUI_TIMEOUT","slow"),"COMFYUI_TIMEOUT",504),(ComfyUIClientError("COMFYUI_SUBMIT_FAILED","bad"),"COMFYUI_SUBMIT_FAILED",502),(ComfyUIClientError("COMFYUI_INVALID_RESPONSE","bad"),"COMFYUI_INVALID_RESPONSE",502),(ComfyUIClientError("COMFYUI_REQUEST_INVALID","bad"),"COMFYUI_REQUEST_INVALID",400)])
def test_generate_route_maps_failed_job_errors(api,monkeypatch,error,code,status):
    scene,workflow=_deps(api)
    def fail(_): raise error
    monkeypatch.setattr(generation_service,"load_workflow_template",fail)
    response=_post(f"/api/v1/scenes/{scene.id}/generate",{"workflow_template_id":workflow.id})
    assert response.status_code==status and response.json()["error"]["code"]==code
    with api() as s:
        job=s.scalar(select(GenerationJob)); assert job.status=="failed" and job.error_code==code and job.finished_at is not None
