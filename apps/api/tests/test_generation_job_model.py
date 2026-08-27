from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect, select

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory
from app.models.generation_job import GenerationJob
from app.models.project import Project
from app.models.scene import Scene
from app.models.workflow_template import WorkflowTemplate
from app.schemas.generation_job import GenerationJobCreate, GenerationJobRead


def _assert_utc(value: datetime) -> None:
    assert value.tzinfo is not None
    assert value.utcoffset() is not None
    assert value.utcoffset().total_seconds() == 0


def _project() -> Project:
    return Project(
        name="Generation project",
        description=None,
        aspect_ratio="16:9",
        width=1920,
        height=1080,
        fps=24,
    )


def _scene(project_id: str) -> Scene:
    return Scene(
        project_id=project_id,
        scene_number=1,
        title="Generation scene",
        description=None,
        prompt="Original prompt",
        negative_prompt="Original negative prompt",
        seed=10,
        duration_seconds=5.0,
        workflow_template_id=None,
        selected_asset_id=None,
        status="draft",
    )


def _workflow_template() -> WorkflowTemplate:
    return WorkflowTemplate(
        name="Demo workflow",
        slug="demo-workflow",
        version="1.0.0",
        template_path="demo/template.json",
        manifest_path="demo/manifest.json",
    )


def _job(project_id: str, scene_id: str, workflow_template_id: str, **overrides: object) -> GenerationJob:
    values = {
        "project_id": project_id,
        "scene_id": scene_id,
        "workflow_template_id": workflow_template_id,
        "workflow_version": "1.0.0",
        "prompt_snapshot": "Snapshot prompt",
        "negative_prompt_snapshot": None,
        "seed": None,
        "params_json": {"frames": 81, "cfg": 5, "nested": {"x": True}},
    }
    values.update(overrides)
    return GenerationJob(**values)


def _create_dependencies(session) -> tuple[Project, Scene, WorkflowTemplate]:
    project = _project()
    session.add(project)
    session.commit()

    scene = _scene(project.id)
    workflow_template = _workflow_template()
    session.add_all([scene, workflow_template])
    session.commit()
    return project, scene, workflow_template


def test_generation_job_orm_round_trip_snapshots_and_schema(tmp_path) -> None:
    database_engine = create_engine_for_path(tmp_path / "generation_job.db")

    try:
        init_db(database_engine)
        table_names = set(inspect(database_engine).get_table_names())
        assert "generation_jobs" in table_names
        assert "generation_outputs" not in table_names

        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            project, scene, workflow_template = _create_dependencies(session)
            job = _job(project.id, scene.id, workflow_template.id)
            session.add(job)
            session.commit()
            session.refresh(job)

            assert isinstance(job.id, str)
            UUID(job.id)
            assert job.project_id == project.id
            assert job.scene_id == scene.id
            assert job.workflow_template_id == workflow_template.id
            assert job.status == "pending"
            assert job.comfy_prompt_id is None
            assert job.workflow_version == "1.0.0"
            assert job.prompt_snapshot == "Snapshot prompt"
            assert job.negative_prompt_snapshot is None
            assert job.seed is None
            assert job.params_json == {"frames": 81, "cfg": 5, "nested": {"x": True}}
            assert job.error_code is None
            assert job.error_message is None
            assert job.started_at is None
            assert job.finished_at is None
            _assert_utc(job.created_at)

            workflow_template.version = "2.0.0"
            scene.prompt = "Updated scene prompt"
            job.comfy_prompt_id = "prompt-123"
            job.error_code = "CUDA_OOM"
            job.error_message = "CUDA out of memory"
            session.commit()
            session.refresh(job)

            loaded_job = session.scalar(select(GenerationJob).where(GenerationJob.id == job.id))
            assert loaded_job is not None
            assert loaded_job.workflow_version == "1.0.0"
            assert loaded_job.prompt_snapshot == "Snapshot prompt"
            assert loaded_job.comfy_prompt_id == "prompt-123"
            assert loaded_job.error_code == "CUDA_OOM"
            assert loaded_job.error_message == "CUDA out of memory"

            read = GenerationJobRead.model_validate(job)
            assert read.id == job.id
            assert read.project_id == project.id
            assert read.status == "pending"
            assert read.params_json == job.params_json
            assert read.created_at == job.created_at
    finally:
        database_engine.dispose()


def test_generation_job_params_default_is_independent(tmp_path) -> None:
    database_engine = create_engine_for_path(tmp_path / "generation_job.db")

    try:
        init_db(database_engine)
        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            project, scene, workflow_template = _create_dependencies(session)
            first = GenerationJob(
                project_id=project.id,
                scene_id=scene.id,
                workflow_template_id=workflow_template.id,
                workflow_version="1.0.0",
                prompt_snapshot="First prompt",
            )
            second = GenerationJob(
                project_id=project.id,
                scene_id=scene.id,
                workflow_template_id=workflow_template.id,
                workflow_version="1.0.0",
                prompt_snapshot="Second prompt",
            )
            session.add_all([first, second])
            session.commit()

            first.params_json["cfg"] = 5
            assert second.params_json == {}
    finally:
        database_engine.dispose()


@pytest.mark.parametrize(
    "status",
    ["pending", "queued", "running", "completed", "failed", "cancelled"],
)
def test_generation_job_create_schema_accepts_valid_statuses(status: str) -> None:
    create = GenerationJobCreate(
        project_id="project-id",
        scene_id="scene-id",
        workflow_template_id="workflow-id",
        workflow_version="1.0.0",
        prompt_snapshot="",
        params_json={},
        status=status,
    )

    assert create.status == status


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "processing"},
        {"workflow_version": "   "},
        {"seed": True},
        {"params_json": []},
    ],
)
def test_generation_job_create_schema_rejects_invalid_values(overrides: dict[str, object]) -> None:
    values = {
        "project_id": "project-id",
        "scene_id": "scene-id",
        "workflow_template_id": "workflow-id",
        "workflow_version": "1.0.0",
        "prompt_snapshot": "Snapshot prompt",
        "negative_prompt_snapshot": None,
        "seed": 123456,
        "params_json": {},
    }
    values.update(overrides)

    with pytest.raises(ValidationError):
        GenerationJobCreate(**values)
