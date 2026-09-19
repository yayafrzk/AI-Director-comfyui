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
from app.services.generation_service import GenerationServiceError, retry_generation, submit_generation
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
            assert job.seed == 222 and job.params_json == {"cfg": 5, "duration_seconds": 1, "megapixels": 0.6}
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

def _loaded_with_scene_parameters(include_scene_parameters: bool = True) -> LoadedWorkflowTemplate:
    inputs = {
        "prompt": {"node_id": "1", "field": "text", "required": True},
        "seed": {"node_id": "2", "field": "noise_seed"},
    }
    template = {
        "1": {"inputs": {"text": ""}},
        "2": {"inputs": {"noise_seed": 0}},
    }
    if include_scene_parameters:
        inputs["duration_seconds"] = {
            "node_id": "3",
            "field": "value",
            "type": "float",
        }
        inputs["megapixels"] = {
            "node_id": "4",
            "field": "megapixels",
            "type": "float",
        }
        template["3"] = {"inputs": {"value": 9.0}}
        template["4"] = {"inputs": {"megapixels": 0.6}}
    return LoadedWorkflowTemplate(
        template=template,
        manifest=WorkflowManifest.model_validate(
            {"id": "w", "name": "W", "version": "1.0.0", "inputs": inputs}
        ),
    )


class _ListenerTask:
    def cancel(self) -> None:
        return None


def _mock_successful_queue(monkeypatch, loaded: LoadedWorkflowTemplate, built_params: list[dict]) -> None:
    monkeypatch.setattr(generation_service, "_start_listener", lambda *_: _ListenerTask())
    monkeypatch.setattr(generation_service, "load_workflow_template", lambda _: loaded)
    monkeypatch.setattr(
        generation_service,
        "build_workflow",
        lambda _loaded, params: built_params.append(params) or {"built": True},
    )

    async def submit(_workflow, client_id=None):
        assert client_id
        return f"prompt-{len(built_params)}"

    monkeypatch.setattr(generation_service, "submit_prompt", submit)


def test_submit_generation_uses_request_seed_before_scene_seed_and_snapshots_parameters(tmp_path, monkeypatch) -> None:
    engine = create_engine_for_path(tmp_path / "request-seed.sqlite")
    init_db(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            scene, workflow = _dependencies(session)
            scene.duration_seconds = 5.0
            scene.megapixels = 0.8
            session.commit()
            built_params: list[dict] = []
            _mock_successful_queue(monkeypatch, _loaded_with_scene_parameters(), built_params)

            job = asyncio.run(submit_generation(session, scene, workflow, 222, {"cfg": 5}))

            assert job.seed == 222
            assert job.params_json == {
                "cfg": 5,
                "duration_seconds": 5.0,
                "megapixels": 0.8,
            }
            assert built_params == [
                {
                    "cfg": 5,
                    "prompt": "prompt",
                    "seed": 222,
                    "duration_seconds": 5.0,
                    "megapixels": 0.8,
                }
            ]
    finally:
        engine.dispose()


def test_submit_generation_uses_scene_seed_when_request_seed_is_missing(tmp_path, monkeypatch) -> None:
    engine = create_engine_for_path(tmp_path / "scene-seed.sqlite")
    init_db(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            scene, workflow = _dependencies(session)
            built_params: list[dict] = []
            _mock_successful_queue(monkeypatch, _loaded_with_scene_parameters(), built_params)
            monkeypatch.setattr(generation_service, "_random_seed", lambda: 999)

            job = asyncio.run(submit_generation(session, scene, workflow, None, {}))

            assert job.seed == 111
            assert built_params[0]["seed"] == 111
    finally:
        engine.dispose()


def test_submit_generation_uses_new_random_seed_without_mutating_scene(tmp_path, monkeypatch) -> None:
    engine = create_engine_for_path(tmp_path / "random-seed.sqlite")
    init_db(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            scene, workflow = _dependencies(session)
            scene.seed = None
            session.commit()
            built_params: list[dict] = []
            _mock_successful_queue(monkeypatch, _loaded_with_scene_parameters(), built_params)
            monkeypatch.setattr(generation_service, "_random_seed", lambda: 333)

            job = asyncio.run(submit_generation(session, scene, workflow, None, {}))

            assert job.seed == 333
            assert built_params[0]["seed"] == 333
            assert session.get(Scene, scene.id).seed is None
    finally:
        engine.dispose()


def test_new_generation_uses_a_fresh_random_seed_and_retry_reuses_snapshot(tmp_path, monkeypatch) -> None:
    engine = create_engine_for_path(tmp_path / "retry-seed.sqlite")
    init_db(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            scene, workflow = _dependencies(session)
            scene.seed = None
            session.commit()
            built_params: list[dict] = []
            _mock_successful_queue(monkeypatch, _loaded_with_scene_parameters(), built_params)
            seeds = iter((333, 444))
            monkeypatch.setattr(generation_service, "_random_seed", lambda: next(seeds))

            first_job = asyncio.run(submit_generation(session, scene, workflow, None, {}))
            second_job = asyncio.run(submit_generation(session, scene, workflow, None, {}))
            assert (first_job.seed, second_job.seed) == (333, 444)

            first_job.status = "failed"
            session.commit()
            retry_job = asyncio.run(retry_generation(session, first_job.id))

            assert retry_job.seed == 333
            assert retry_job.params_json == first_job.params_json
    finally:
        engine.dispose()


def test_scene_parameters_are_omitted_for_workflows_that_do_not_declare_them(tmp_path, monkeypatch) -> None:
    engine = create_engine_for_path(tmp_path / "legacy-workflow.sqlite")
    init_db(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            scene, workflow = _dependencies(session)
            built_params: list[dict] = []
            _mock_successful_queue(
                monkeypatch,
                _loaded_with_scene_parameters(include_scene_parameters=False),
                built_params,
            )

            job = asyncio.run(submit_generation(session, scene, workflow, None, {}))

            assert job.params_json["duration_seconds"] == 1
            assert job.params_json["megapixels"] == 0.6
            assert built_params == [{"prompt": "prompt", "seed": 111}]
    finally:
        engine.dispose()


def test_submit_generation_rejects_scene_parameter_overrides_and_unknown_caller_params(tmp_path, monkeypatch) -> None:
    engine = create_engine_for_path(tmp_path / "reserved-parameters.sqlite")
    init_db(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            scene, workflow = _dependencies(session)
            for parameter_name in ("duration_seconds", "megapixels"):
                with pytest.raises(GenerationServiceError) as error:
                    asyncio.run(
                        submit_generation(session, scene, workflow, None, {parameter_name: 1})
                    )
                assert error.value.code == "GENERATION_PARAMS_INVALID"

            monkeypatch.setattr(generation_service, "_start_listener", lambda *_: _ListenerTask())
            monkeypatch.setattr(
                generation_service,
                "load_workflow_template",
                lambda _: _loaded_with_scene_parameters(include_scene_parameters=False),
            )
            with pytest.raises(GenerationServiceError) as error:
                asyncio.run(submit_generation(session, scene, workflow, None, {"unknown": 1}))
            assert error.value.code == "WORKFLOW_INPUT_UNKNOWN"
    finally:
        engine.dispose()
