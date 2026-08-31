import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

import app.services.generation_service as generation_service
from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory
from app.models.generation_job import GenerationJob
from app.models.project import Project
from app.models.scene import Scene
from app.models.workflow_template import WorkflowTemplate
from app.schemas.workflow_manifest import WorkflowManifest
from app.services.comfyui_client import ComfyUIClientError
from app.services.generation_service import GenerationServiceError, cancel_generation, retry_generation
from app.services.workflow_loader import LoadedWorkflowTemplate


def _dependencies(session):
    project = Project(name="Actions", description=None, aspect_ratio="16:9", width=1, height=1, fps=24)
    session.add(project)
    session.flush()
    scene = Scene(project_id=project.id, scene_number=1, title="Scene", description=None, prompt="old prompt", negative_prompt="old negative", seed=11, duration_seconds=1, workflow_template_id=None, selected_asset_id=None, status="draft")
    workflow = WorkflowTemplate(name="Workflow", slug="actions-workflow", version="1", template_path="x", manifest_path="y")
    session.add_all([scene, workflow])
    session.flush()
    return project, scene, workflow


def _job(session, project, scene, workflow, status: str, prompt_id: str | None = "prompt-1"):
    job = GenerationJob(project_id=project.id, scene_id=scene.id, workflow_template_id=workflow.id, workflow_version="1", prompt_snapshot="snapshot prompt", negative_prompt_snapshot="snapshot negative", seed=22, params_json={"cfg": 5}, comfy_prompt_id=prompt_id, status=status, error_code="OLD_ERROR" if status == "failed" else None, error_message="old message" if status == "failed" else None, finished_at=datetime(2025, 1, 1, tzinfo=timezone.utc) if status == "failed" else None)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@pytest.mark.parametrize(("status", "prompt_id", "expected_calls"), [("pending", None, []), ("queued", "queued-prompt", [("queued-prompt", True)]), ("running", "running-prompt", [("running-prompt", False)])])
def test_cancel_generation_handles_cancellable_states(tmp_path, monkeypatch, status, prompt_id, expected_calls):
    engine = create_engine_for_path(tmp_path / "cancel.db")
    init_db(engine)
    factory = create_session_factory(engine)
    calls = []

    async def cancel_prompt(value, *, allow_queue_fallback):
        calls.append((value, allow_queue_fallback))

    monkeypatch.setattr(generation_service, "cancel_prompt", cancel_prompt)
    try:
        with factory() as session:
            project, scene, workflow = _dependencies(session)
            job = _job(session, project, scene, workflow, status, prompt_id)
            cancelled = asyncio.run(cancel_generation(session, job.id))
            assert cancelled.status == "cancelled"
            assert cancelled.finished_at is not None
        assert calls == expected_calls
    finally:
        engine.dispose()


def test_cancel_generation_is_idempotent_and_rejects_terminal_jobs(tmp_path, monkeypatch):
    engine = create_engine_for_path(tmp_path / "cancel-terminal.db")
    init_db(engine)
    factory = create_session_factory(engine)

    async def unexpected(*_args, **_kwargs):
        raise AssertionError("terminal jobs must not call ComfyUI")

    monkeypatch.setattr(generation_service, "cancel_prompt", unexpected)
    try:
        with factory() as session:
            project, scene, workflow = _dependencies(session)
            already_cancelled = _job(session, project, scene, workflow, "cancelled")
            assert asyncio.run(cancel_generation(session, already_cancelled.id)).status == "cancelled"
            for status in ("completed", "failed"):
                job = _job(session, project, scene, workflow, status)
                with pytest.raises(GenerationServiceError) as error:
                    asyncio.run(cancel_generation(session, job.id))
                assert error.value.code == "GENERATION_JOB_NOT_CANCELLABLE"
                assert session.get(GenerationJob, job.id).status == status
            with pytest.raises(GenerationServiceError) as missing:
                asyncio.run(cancel_generation(session, "missing"))
            assert missing.value.code == "GENERATION_JOB_NOT_FOUND"
    finally:
        engine.dispose()


def _loaded():
    return LoadedWorkflowTemplate(template={"1": {"inputs": {"text": "", "seed": 0}}}, manifest=WorkflowManifest.model_validate({"id": "actions-workflow", "name": "Workflow", "version": "1", "inputs": {"prompt": {"node_id": "1", "field": "text", "required": True}, "seed": {"node_id": "1", "field": "seed", "type": "integer", "required": True}}}))


def test_retry_creates_new_queued_job_from_snapshot_and_preserves_original(tmp_path, monkeypatch):
    engine = create_engine_for_path(tmp_path / "retry.db")
    init_db(engine)
    factory = create_session_factory(engine)
    seen_params = []

    class ListenerTask:
        def cancel(self):
            return None

    async def submit(_workflow, client_id=None):
        assert client_id
        return "retry-prompt"

    monkeypatch.setattr(generation_service, "_start_listener", lambda *_args: ListenerTask())
    monkeypatch.setattr(generation_service, "load_workflow_template", lambda _template: _loaded())
    monkeypatch.setattr(generation_service, "build_workflow", lambda _loaded_workflow, params: seen_params.append(params) or {"built": True})
    monkeypatch.setattr(generation_service, "submit_prompt", submit)
    try:
        with factory() as session:
            project, scene, workflow = _dependencies(session)
            original = _job(session, project, scene, workflow, "failed", "old-prompt")
            original_values = (original.id, original.status, original.error_code, original.error_message, original.finished_at, original.comfy_prompt_id)
            scene.prompt = "changed prompt"
            scene.seed = 999
            session.commit()
            retried = asyncio.run(retry_generation(session, original.id))
            assert retried.id != original.id
            assert retried.status == "queued"
            assert retried.comfy_prompt_id == "retry-prompt"
            assert (retried.project_id, retried.scene_id, retried.workflow_template_id, retried.workflow_version, retried.prompt_snapshot, retried.negative_prompt_snapshot, retried.seed, retried.params_json) == (original.project_id, original.scene_id, original.workflow_template_id, original.workflow_version, "snapshot prompt", "snapshot negative", 22, {"cfg": 5})
            assert seen_params == [{"cfg": 5, "prompt": "snapshot prompt", "seed": 22}]
            session.refresh(original)
            assert (original.id, original.status, original.error_code, original.error_message, original.finished_at, original.comfy_prompt_id) == original_values
            assert session.scalars(select(GenerationJob).where(GenerationJob.id == retried.id)).one().outputs == []
    finally:
        engine.dispose()


def test_retry_submission_failure_creates_failed_new_job_without_changing_original(tmp_path, monkeypatch):
    engine = create_engine_for_path(tmp_path / "retry-failure.db")
    init_db(engine)
    factory = create_session_factory(engine)

    class ListenerTask:
        def cancel(self):
            return None

    async def fail_submit(_workflow, client_id=None):
        raise ComfyUIClientError("COMFYUI_OFFLINE", "offline")

    monkeypatch.setattr(generation_service, "_start_listener", lambda *_args: ListenerTask())
    monkeypatch.setattr(generation_service, "load_workflow_template", lambda _template: _loaded())
    monkeypatch.setattr(generation_service, "build_workflow", lambda *_args: {"built": True})
    monkeypatch.setattr(generation_service, "submit_prompt", fail_submit)
    try:
        with factory() as session:
            project, scene, workflow = _dependencies(session)
            original = _job(session, project, scene, workflow, "failed", "old-prompt")
            with pytest.raises(GenerationServiceError) as error:
                asyncio.run(retry_generation(session, original.id))
            assert error.value.code == "COMFYUI_OFFLINE"
            session.refresh(original)
            assert original.status == "failed" and original.error_message == "old message"
            jobs = session.scalars(select(GenerationJob).order_by(GenerationJob.created_at)).all()
            assert len(jobs) == 2 and jobs[1].status == "failed" and jobs[1].id != original.id
    finally:
        engine.dispose()

def test_running_cancel_unsupported_keeps_job_running(tmp_path, monkeypatch):
    engine = create_engine_for_path(tmp_path / "cancel-unsupported.db")
    init_db(engine)
    factory = create_session_factory(engine)

    async def unsupported(*_args, **_kwargs):
        raise ComfyUIClientError("COMFYUI_RUNNING_CANCEL_UNSUPPORTED", "unsupported")

    monkeypatch.setattr(generation_service, "cancel_prompt", unsupported)
    try:
        with factory() as session:
            project, scene, workflow = _dependencies(session)
            job = _job(session, project, scene, workflow, "running", "running-prompt")
            with pytest.raises(GenerationServiceError) as error:
                asyncio.run(cancel_generation(session, job.id))
            assert error.value.code == "COMFYUI_RUNNING_CANCEL_UNSUPPORTED"
            session.refresh(job)
            assert job.status == "running" and job.finished_at is None
    finally:
        engine.dispose()


@pytest.mark.parametrize("status", ["completed", "running", "queued"])
def test_retry_rejects_nonfailed_jobs(tmp_path, status):
    engine = create_engine_for_path(tmp_path / f"retry-{status}.db")
    init_db(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            project, scene, workflow = _dependencies(session)
            job = _job(session, project, scene, workflow, status)
            with pytest.raises(GenerationServiceError) as error:
                asyncio.run(retry_generation(session, job.id))
            assert error.value.code == "GENERATION_JOB_NOT_RETRYABLE"
            assert session.get(GenerationJob, job.id).status == status
    finally:
        engine.dispose()

def test_cancel_not_applied_keeps_queued_job_unchanged(tmp_path, monkeypatch):
    engine = create_engine_for_path(tmp_path / "cancel-not-applied.db")
    init_db(engine)
    factory = create_session_factory(engine)

    async def not_applied(*_args, **_kwargs):
        raise ComfyUIClientError("COMFYUI_CANCEL_NOT_APPLIED", "not applied")

    monkeypatch.setattr(generation_service, "cancel_prompt", not_applied)
    try:
        with factory() as session:
            project, scene, workflow = _dependencies(session)
            job = _job(session, project, scene, workflow, "queued", "queued-prompt")
            with pytest.raises(GenerationServiceError) as error:
                asyncio.run(cancel_generation(session, job.id))
            assert error.value.code == "COMFYUI_CANCEL_NOT_APPLIED"
            session.refresh(job)
            assert job.status == "queued" and job.finished_at is None
    finally:
        engine.dispose()
