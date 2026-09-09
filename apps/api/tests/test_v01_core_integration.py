import asyncio
import io
import json
from pathlib import Path, PureWindowsPath
from unittest.mock import AsyncMock, Mock
import zipfile

import httpx
import pytest
from sqlalchemy import select

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory, get_db
from app.main import app
from app.models.asset import Asset
from app.models.generation_job import GenerationJob
from app.models.generation_output import GenerationOutput
from app.models.workflow_template import WorkflowTemplate
from app.schemas.workflow_manifest import WorkflowManifest
from app.services import generation_archive, generation_service
from app.services.workflow_loader import LoadedWorkflowTemplate


@pytest.fixture
def integration_environment(tmp_path, monkeypatch):
    app_data_dir = tmp_path / "V0.1 集成 数据"
    app_data_dir.mkdir()
    monkeypatch.setenv("APP_DATA_DIR", str(app_data_dir))
    engine = create_engine_for_path(app_data_dir / "ai_director.db")
    session_factory = create_session_factory(engine)

    def override_get_db():
        with session_factory() as session:
            yield session

    previous_override = app.dependency_overrides.get(get_db)
    try:
        init_db(engine)
        app.dependency_overrides[get_db] = override_get_db
        monkeypatch.setattr(generation_archive, "SessionLocal", session_factory)
        yield session_factory, app_data_dir
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
        engine.dispose()


def _success_data(response, expected_status=200):
    assert response.status_code == expected_status, response.text
    payload = response.json()
    assert payload["error"] is None
    return payload["data"]


def test_v01_core_pipeline_from_project_to_download(integration_environment, monkeypatch):
    session_factory, app_data_dir = integration_environment
    scene_inputs = [
        {"title": "第一幕", "prompt": "prompt-one", "seed": 101, "duration_seconds": 5},
        {"title": "第二幕", "prompt": "prompt-two", "seed": 202, "duration_seconds": 6},
    ]
    prompt_ids = ["prompt-001", "prompt-002"]
    output_names = ["第一幕-output.mp4", "第二幕-output.mp4"]
    video_bytes = [b"scene-one-video", b"scene-two-video"]
    export_names = ["01_第一幕.mp4", "02_第二幕.mp4"]
    loaded = LoadedWorkflowTemplate(
        {"10": {"inputs": {}}},
        WorkflowManifest.model_validate({
            "id": "integration-workflow",
            "name": "Integration Workflow",
            "version": "1",
            "inputs": {},
        }),
    )
    load_mock = Mock(return_value=loaded)
    build_mock = Mock(return_value={"10": {"inputs": {}}})
    submit_mock = AsyncMock(side_effect=prompt_ids)

    async def receive_prompt_id(job_id, client_id, prompt_id_future):
        assert job_id and client_id
        assert await prompt_id_future in prompt_ids

    listener_mock = AsyncMock(side_effect=receive_prompt_id)

    async def history(prompt_id):
        index = prompt_ids.index(prompt_id)
        return {
            prompt_id: {
                "outputs": {
                    "10": {
                        "videos": [{
                            "filename": output_names[index],
                            "subfolder": "",
                            "type": "output",
                        }],
                    },
                },
            },
        }

    async def download(filename, subfolder, output_type):
        assert subfolder == ""
        assert output_type == "output"
        return video_bytes[output_names.index(filename)]

    history_mock = AsyncMock(side_effect=history)
    download_mock = AsyncMock(side_effect=download)
    monkeypatch.setattr(generation_service, "load_workflow_template", load_mock)
    monkeypatch.setattr(generation_service, "build_workflow", build_mock)
    monkeypatch.setattr(generation_service, "submit_prompt", submit_mock)
    monkeypatch.setattr(generation_service, "listen_for_generation", listener_mock)
    monkeypatch.setattr(generation_archive, "get_history", history_mock)
    monkeypatch.setattr(generation_archive, "download_output", download_mock)

    async def run_pipeline():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Project: create through the real API.
            project = _success_data(await client.post("/api/v1/projects", json={
                "name": "V0.1 集成项目",
                "description": "core integration",
                "aspect_ratio": "16:9",
                "width": 1920,
                "height": 1080,
                "fps": 24,
            }), 201)
            project_id = project["id"]
            assert project_id
            assert project["name"] == "V0.1 集成项目"

            # Scenes: real API assigns both scene numbers.
            scenes = []
            for scene_input in scene_inputs:
                scenes.append(_success_data(await client.post(
                    f"/api/v1/projects/{project_id}/scenes", json=scene_input,
                ), 201))
            scene_ids = [scene["id"] for scene in scenes]
            assert len(set(scene_ids)) == 2
            assert [scene["scene_number"] for scene in scenes] == [1, 2]

            # Workflow: the only directly inserted test row.
            with session_factory() as session:
                workflow = WorkflowTemplate(
                    name="Integration Workflow", slug="integration-workflow", version="1",
                    template_path="dummy/template.json", manifest_path="dummy/manifest.json",
                    is_enabled=True,
                )
                session.add(workflow)
                session.commit()
                workflow_id = workflow.id

            # Binding: PATCH and GET prove persistence for both scenes.
            for scene_id in scene_ids:
                bound = _success_data(await client.patch(
                    f"/api/v1/scenes/{scene_id}", json={"workflow_template_id": workflow_id},
                ))
                assert bound["workflow_template_id"] == workflow_id
                refreshed = _success_data(await client.get(f"/api/v1/scenes/{scene_id}"))
                assert refreshed["workflow_template_id"] == workflow_id

            # Generate: real GenerationService persists queued jobs.
            job_ids = []
            for scene_id in scene_ids:
                submitted = _success_data(await client.post(
                    f"/api/v1/scenes/{scene_id}/generate",
                    json={"workflow_template_id": workflow_id, "params": {}},
                ))
                assert submitted["status"] == "queued"
                assert submitted["job_id"]
                job_ids.append(submitted["job_id"])
            assert len(set(job_ids)) == 2

            # Drain only this test's listener tasks on the same event loop.
            listeners = [
                task for task in generation_service._background_tasks
                if task.get_loop() is asyncio.get_running_loop()
            ]
            await asyncio.gather(*listeners)
            assert listener_mock.await_count == 2
            assert submit_mock.await_count == 2
            assert load_mock.call_count == build_mock.call_count == 2
            for index, call in enumerate(submit_mock.await_args_list):
                assert call.kwargs["client_id"]
                listener_call = listener_mock.await_args_list[index]
                assert listener_call.args[1] == call.kwargs["client_id"]

            with session_factory() as session:
                assert len(session.scalars(select(GenerationJob)).all()) == 2
                for index, job_id in enumerate(job_ids):
                    job = session.get(GenerationJob, job_id)
                    assert job is not None
                    assert job.project_id == project_id
                    assert job.scene_id == scene_ids[index]
                    assert job.workflow_template_id == workflow_id
                    assert job.workflow_version == "1"
                    assert job.status == "queued"
                    assert job.comfy_prompt_id == prompt_ids[index]
                    assert job.prompt_snapshot == scene_inputs[index]["prompt"]
                    assert job.seed == scene_inputs[index]["seed"]

            # Archive: real service creates files, Assets and GenerationOutputs.
            for index, job_id in enumerate(job_ids):
                event = await generation_archive.archive_generation(job_id)
                assert event == {
                    "type": "generation.completed", "job_id": job_id,
                    "scene_id": scene_ids[index], "status": "completed",
                }
            assert history_mock.await_count == download_mock.await_count == 2
            assert [call.args[0] for call in history_mock.await_args_list] == prompt_ids
            assert [call.args[0] for call in download_mock.await_args_list] == output_names

            project_root = app_data_dir / "projects" / project_id
            with session_factory() as session:
                assert len(session.scalars(select(GenerationOutput)).all()) == 2
                assert len(session.scalars(select(Asset)).all()) == 2
                for index, job_id in enumerate(job_ids):
                    job = session.get(GenerationJob, job_id)
                    assert job.status == "completed"
                    assert len(job.outputs) == 1
                    output = job.outputs[0]
                    assert output.output_index == 0
                    asset = output.asset
                    assert asset.role == "output"
                    assert asset.type == "video"
                    assert asset.scene_id == scene_ids[index]
                    assert asset.project_id == project_id
                    relative = Path(asset.relative_path)
                    assert not relative.is_absolute()
                    assert not PureWindowsPath(asset.relative_path).is_absolute()
                    assert relative.parts[0] == "videos"
                    archived_path = (project_root / relative).resolve()
                    assert archived_path.is_relative_to(project_root.resolve())
                    assert archived_path.read_bytes() == video_bytes[index]

            # History: use public response Asset IDs for selecting final versions.
            asset_ids = []
            for index, scene_id in enumerate(scene_ids):
                jobs = _success_data(await client.get(
                    f"/api/v1/scenes/{scene_id}/generation-jobs",
                ))
                assert len(jobs) == 1
                assert jobs[0]["id"] == job_ids[index]
                assert jobs[0]["status"] == "completed"
                assert len(jobs[0]["outputs"]) == 1
                output = jobs[0]["outputs"][0]
                assert output["output_index"] == 0
                assert output["asset"]["type"] == "video"
                assert output["asset"]["role"] == "output"
                assert output["asset"]["mime_type"] == "video/mp4"
                assert output["asset"]["id"]
                asset_ids.append(output["asset"]["id"])
            assert len(set(asset_ids)) == 2

            # Select: real API, then GET to verify the saved selection.
            for scene_id, asset_id in zip(scene_ids, asset_ids):
                selected = _success_data(await client.post(
                    f"/api/v1/scenes/{scene_id}/assets/{asset_id}/select",
                ))
                assert selected["selected_asset_id"] == asset_id
                refreshed = _success_data(await client.get(f"/api/v1/scenes/{scene_id}"))
                assert refreshed["selected_asset_id"] == asset_id

            # Export: validate order, exact filenames and copied bytes.
            exported = _success_data(await client.post(f"/api/v1/projects/{project_id}/export"))
            assert exported["project_id"] == project_id
            assert exported["export_id"]
            assert exported["manifest_filename"] == "manifest.json"
            assert [item["scene_number"] for item in exported["files"]] == [1, 2]
            assert [item["asset_id"] for item in exported["files"]] == asset_ids
            assert [item["filename"] for item in exported["files"]] == export_names
            assert not Path(exported["export_dir"]).is_absolute()
            export_directory = app_data_dir / exported["export_dir"]
            expected_entries = export_names + ["manifest.json"]
            assert sorted(path.name for path in export_directory.iterdir()) == expected_entries
            for filename, content in zip(export_names, video_bytes):
                assert (export_directory / filename).read_bytes() == content

            # Manifest: inspect the actual UTF-8 file created by Export.
            manifest_bytes = (export_directory / "manifest.json").read_bytes()
            manifest = json.loads(manifest_bytes.decode("utf-8"))
            assert manifest["schema_version"] == 1
            assert manifest["project"] == {
                "id": project_id, "name": "V0.1 集成项目", "aspect_ratio": "16:9",
                "width": 1920, "height": 1080, "fps": 24,
            }
            assert manifest["export"]["export_id"] == exported["export_id"]
            assert manifest["export"]["created_at"]
            manifest_scenes = manifest["scenes"]
            assert len(manifest_scenes) == 2
            assert [item["scene_number"] for item in manifest_scenes] == [1, 2]
            assert [item["scene_id"] for item in manifest_scenes] == scene_ids
            assert [item["selected_asset_id"] for item in manifest_scenes] == asset_ids
            assert [item["filename"] for item in manifest_scenes] == export_names
            for item, content in zip(manifest_scenes, video_bytes):
                assert item["asset"]["type"] == "video"
                assert item["asset"]["mime_type"] == "video/mp4"
                assert item["asset"]["size_bytes"] == len(content)

            # Download: inspect ZIP bytes returned by the real API.
            response = await client.get(
                f"/api/v1/projects/{project_id}/exports/{exported['export_id']}/download",
            )
            assert response.status_code == 200, response.text
            assert response.headers["content-type"].startswith("application/zip")
            assert f"export-{exported['export_id']}.zip" in response.headers["content-disposition"]
            with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
                assert sorted(bundle.namelist()) == expected_entries
                for name in bundle.namelist():
                    assert "/" not in name and "\\" not in name and ".." not in name
                for filename, content in zip(export_names, video_bytes):
                    assert bundle.read(filename) == content
                assert bundle.read("manifest.json") == manifest_bytes

            # Temp cleanup: response background task removes only the temporary ZIP.
            temporary_directory = app_data_dir / "tmp" / "exports"
            assert not temporary_directory.exists() or list(temporary_directory.iterdir()) == []
            assert export_directory.is_dir()
            assert sorted(path.name for path in export_directory.iterdir()) == expected_entries

    asyncio.run(run_pipeline())
