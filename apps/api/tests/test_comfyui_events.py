import asyncio
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
        project = Project(name=f"Project{suffix}", description=None, aspect_ratio="16:9", width=1, height=1, fps=24)
        session.add(project)
        session.commit()
        scene = Scene(project_id=project.id, scene_number=1, title="Scene", description=None, prompt="p", negative_prompt=None, seed=None, duration_seconds=1, workflow_template_id=None, selected_asset_id=None, status="draft")
        workflow = WorkflowTemplate(name=f"Workflow{suffix}", slug=f"workflow{suffix}", version="1", template_path="x", manifest_path="y")
        session.add_all([scene, workflow])
        session.commit()
        job = GenerationJob(project_id=project.id, scene_id=scene.id, workflow_template_id=workflow.id, workflow_version="1", prompt_snapshot="p", negative_prompt_snapshot=None, seed=None, params_json={}, comfy_prompt_id="prompt-1", status="queued")
        session.add(job)
        session.commit()
        return job.id


def _event(event_type, prompt_id="prompt-1", **data):
    return {"type": event_type, "data": {"prompt_id": prompt_id, **data}}


def test_websocket_url_uses_secure_scheme_and_client_id():
    assert comfyui_events.websocket_url("http://127.0.0.1:8188/", "a b") == "ws://127.0.0.1:8188/ws?clientId=a+b"
    assert comfyui_events.websocket_url("https://comfy.example/api", "client") == "wss://comfy.example/ws?clientId=client"


def test_parse_event_ignores_binary_and_malformed_frames():
    assert comfyui_events.parse_event(b'{"type":"execution_start"}') is None
    assert comfyui_events.parse_event("not json") is None
    assert comfyui_events.parse_event("[]") is None


def test_apply_event_lifecycle_and_terminal_idempotency(tmp_path, monkeypatch):
    engine = create_engine_for_path(tmp_path / "events.db")
    init_db(engine)
    factory = create_session_factory(engine)
    monkeypatch.setattr(comfyui_events, "SessionLocal", factory)
    try:
        job_id = _job(factory)
        comfyui_events.apply_event(job_id, _event("execution_start"))
        with factory() as session:
            job = session.get(GenerationJob, job_id)
            assert job.status == "running" and job.started_at is not None
        comfyui_events.apply_event(job_id, _event("executing"))
        comfyui_events.apply_event(job_id, _event("executed"))
        with factory() as session:
            assert session.get(GenerationJob, job_id).status == "running"
        comfyui_events.apply_event(job_id, _event("execution_success"))
        comfyui_events.apply_event(job_id, _event("execution_error", exception_message="CUDA out of memory"))
        with factory() as session:
            job = session.get(GenerationJob, job_id)
            assert job.status == "completed" and job.finished_at is not None
    finally:
        engine.dispose()


def test_apply_event_error_interrupted_and_wrong_prompt_are_safe(tmp_path, monkeypatch):
    engine = create_engine_for_path(tmp_path / "events.db")
    init_db(engine)
    factory = create_session_factory(engine)
    monkeypatch.setattr(comfyui_events, "SessionLocal", factory)
    try:
        job_id = _job(factory)
        comfyui_events.apply_event(job_id, _event("execution_error", exception_message="CUDA out of memory"))
        with factory() as session:
            job = session.get(GenerationJob, job_id)
            assert job.status == "failed" and job.error_code == "CUDA_OOM" and job.finished_at is not None
        other_job_id = _job(factory, "second")
        comfyui_events.apply_event(other_job_id, _event("execution_interrupted"))
        comfyui_events.apply_event(other_job_id, _event("execution_start", prompt_id="other"))
        with factory() as session:
            assert session.get(GenerationJob, other_job_id).status == "cancelled"
    finally:
        engine.dispose()


class _Socket:
    def __init__(self, messages):
        self.messages = messages

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.messages:
            raise StopAsyncIteration
        return self.messages.pop(0)


def test_listener_filters_frames_and_ignores_disconnect(monkeypatch):
    received = []
    future = asyncio.new_event_loop().create_future()
    future.set_result("prompt-1")
    monkeypatch.setattr(comfyui_events, "apply_event", lambda job_id, event: received.append((job_id, event)))
    socket = _Socket([b"binary", "bad", '{"type":"executing","data":{"prompt_id":"other"}}', '{"type":"executing","data":{"prompt_id":"prompt-1"}}'])
    asyncio.run(comfyui_events.listen_for_generation("job-1", "client-1", future, lambda _: socket))
    assert received == [("job-1", _event("executing"))]

    def disconnected(_):
        raise OSError("connection reset")

    asyncio.run(comfyui_events.listen_for_generation("job-1", "client-1", future, disconnected))


def test_cancelled_job_ignores_late_success_and_progress(tmp_path, monkeypatch):
    engine = create_engine_for_path(tmp_path / "cancelled-events.db")
    init_db(engine)
    factory = create_session_factory(engine)
    monkeypatch.setattr(comfyui_events, "SessionLocal", factory)
    try:
        job_id = _job(factory, "late")
        with factory() as session:
            job = session.get(GenerationJob, job_id)
            job.status = "cancelled"
            job.finished_at = datetime.now(timezone.utc)
            session.commit()
        assert comfyui_events.apply_event(job_id, _event("progress", value=1, max=2)) is None
        assert comfyui_events.apply_event(job_id, _event("execution_start")) is None
        assert comfyui_events.apply_event(job_id, _event("execution_success")) is None
        with factory() as session:
            assert session.get(GenerationJob, job_id).status == "cancelled"
    finally:
        engine.dispose()
