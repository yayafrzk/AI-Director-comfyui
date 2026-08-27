import asyncio

import pytest

import app.services.generation_service as generation_service
from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory
from app.models.generation_job import GenerationJob
from app.models.project import Project
from app.models.scene import Scene
from app.models.workflow_template import WorkflowTemplate
from app.schemas.workflow_manifest import WorkflowManifest
from app.services.generation_service import GenerationServiceError, submit_generation
from app.services.workflow_loader import LoadedWorkflowTemplate, WorkflowLoadError


def _dependencies(session):
    project = Project(name="P", description=None, aspect_ratio="16:9", width=1, height=1, fps=24)
    session.add(project); session.commit()
    scene = Scene(project_id=project.id, scene_number=1, title="S", description=None, prompt="prompt", negative_prompt="negative", seed=111, duration_seconds=1, workflow_template_id=None, selected_asset_id=None, status="draft")
    workflow = WorkflowTemplate(name="W", slug="w", version="1.0.0", template_path="x", manifest_path="y")
    session.add_all([scene, workflow]); session.commit()
    return scene, workflow


def _loaded() -> LoadedWorkflowTemplate:
    return LoadedWorkflowTemplate(template={"1": {"inputs": {"text": ""}}}, manifest=WorkflowManifest.model_validate({"id": "w", "name": "W", "version": "1.0.0", "inputs": {"prompt": {"node_id": "1", "field": "text", "required": True}, "seed": {"node_id": "1", "field": "text"}}}))


def test_submit_generation_persists_pending_then_queues(tmp_path, monkeypatch) -> None:
    engine = create_engine_for_path(tmp_path / "db.sqlite"); init_db(engine); factory = create_session_factory(engine)
    try:
        with factory() as session:
            scene, workflow = _dependencies(session)
            seen = []
            def load(_): return _loaded()
            def build(loaded, params): seen.append(params); return {"built": True}
            async def submit(workflow, client_id=None):
                assert client_id
                assert session.get(GenerationJob, seen and session.scalar(__import__('sqlalchemy').select(GenerationJob.id))) is not None
                return "prompt-123"
            monkeypatch.setattr(generation_service, "load_workflow_template", load)
            monkeypatch.setattr(generation_service, "build_workflow", build)
            monkeypatch.setattr(generation_service, "submit_prompt", submit)
            job = asyncio.run(submit_generation(session, scene, workflow, 222, {"cfg": 5}))
            assert job.status == "queued" and job.comfy_prompt_id == "prompt-123"
            assert job.seed == 222 and job.params_json == {"cfg": 5}
            assert seen == [{"cfg": 5, "prompt": "prompt", "seed": 222}]
            assert scene.status == "draft"
    finally: engine.dispose()


def test_submit_generation_marks_failure_and_rejects_reserved_params(tmp_path, monkeypatch) -> None:
    engine = create_engine_for_path(tmp_path / "db.sqlite"); init_db(engine); factory = create_session_factory(engine)
    try:
        with factory() as session:
            scene, workflow = _dependencies(session)
            with pytest.raises(GenerationServiceError) as reserved:
                asyncio.run(submit_generation(session, scene, workflow, None, {"seed": 1}))
            assert reserved.value.code == "GENERATION_PARAMS_INVALID"
            def fail(_): raise WorkflowLoadError("WORKFLOW_MANIFEST_MISMATCH", "mismatch")
            monkeypatch.setattr(generation_service, "load_workflow_template", fail)
            with pytest.raises(GenerationServiceError) as error:
                asyncio.run(submit_generation(session, scene, workflow, None, {}))
            assert error.value.code == "WORKFLOW_MANIFEST_MISMATCH"
            job = session.scalar(__import__('sqlalchemy').select(GenerationJob))
            assert job.status == "failed" and job.finished_at is not None
    finally: engine.dispose()
