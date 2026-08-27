from datetime import datetime, timezone

import app.services.comfyui_events as comfyui_events
from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory
from app.models.generation_job import GenerationJob
from app.models.project import Project
from app.models.scene import Scene
from app.models.workflow_template import WorkflowTemplate


def _job(factory, suffix=""):
    with factory() as session:
        project = Project(name=f"Events{suffix}", description=None, aspect_ratio="16:9", width=1, height=1, fps=24)
        session.add(project); session.commit()
        scene = Scene(project_id=project.id, scene_number=1, title="Scene", description=None, prompt="p", negative_prompt=None, seed=None, duration_seconds=1, workflow_template_id=None, selected_asset_id=None, status="draft")
        workflow = WorkflowTemplate(name=f"Events workflow{suffix}", slug=f"events-workflow{suffix}", version="1", template_path="x", manifest_path="y")
        session.add_all([scene, workflow]); session.commit()
        job = GenerationJob(project_id=project.id, scene_id=scene.id, workflow_template_id=workflow.id, workflow_version="1", prompt_snapshot="p", negative_prompt_snapshot=None, seed=None, params_json={}, comfy_prompt_id="prompt-1", status="queued")
        session.add(job); session.commit()
        return job.id, scene.id


def _event(event_type, **data):
    return {"type": event_type, "data": {"prompt_id": "prompt-1", **data}}


def test_lifecycle_events_create_frontend_contracts(tmp_path, monkeypatch):
    engine = create_engine_for_path(tmp_path / "events.db"); init_db(engine); factory = create_session_factory(engine)
    monkeypatch.setattr(comfyui_events, "SessionLocal", factory)
    try:
        job_id, scene_id = _job(factory)
        running = comfyui_events.apply_event(job_id, _event("execution_start"))
        assert running == {"type": "generation.running", "job_id": job_id, "scene_id": scene_id, "status": "running"}
        completed = comfyui_events.apply_event(job_id, _event("execution_success"))
        assert completed == {"type": "generation.completed", "job_id": job_id, "scene_id": scene_id, "status": "completed"}
    finally: engine.dispose()


def test_progress_normalizes_bounds_and_invalid_values_are_safe(tmp_path, monkeypatch):
    engine = create_engine_for_path(tmp_path / "events.db"); init_db(engine); factory = create_session_factory(engine)
    monkeypatch.setattr(comfyui_events, "SessionLocal", factory)
    try:
        job_id, scene_id = _job(factory)
        progress = comfyui_events.apply_event(job_id, _event("progress", value=42, max=100, node="38"))
        assert progress == {"type": "generation.progress", "job_id": job_id, "scene_id": scene_id, "status": "queued", "progress": 0.42, "node_id": "38"}
        assert comfyui_events.apply_event(job_id, _event("progress", value=-1, max=100))["progress"] == 0.0
        assert comfyui_events.apply_event(job_id, _event("progress", value=200, max=100))["progress"] == 1.0
        assert comfyui_events.apply_event(job_id, _event("progress", value=1, max=0)) is None
        assert comfyui_events.apply_event(job_id, _event("progress", value="bad", max=100)) is None
    finally: engine.dispose()


def test_failed_and_cancelled_events_include_lifecycle_fields(tmp_path, monkeypatch):
    engine = create_engine_for_path(tmp_path / "events.db"); init_db(engine); factory = create_session_factory(engine)
    monkeypatch.setattr(comfyui_events, "SessionLocal", factory)
    try:
        job_id, scene_id = _job(factory)
        failed = comfyui_events.apply_event(job_id, _event("execution_error", exception_message="CUDA out of memory"))
        assert failed == {"type": "generation.failed", "job_id": job_id, "scene_id": scene_id, "status": "failed", "error_code": "CUDA_OOM", "message": "CUDA out of memory"}
        job_id, scene_id = _job(factory, "cancelled")
        cancelled = comfyui_events.apply_event(job_id, _event("execution_interrupted"))
        assert cancelled == {"type": "generation.cancelled", "job_id": job_id, "scene_id": scene_id, "status": "cancelled"}
    finally: engine.dispose()


