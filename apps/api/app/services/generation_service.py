import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.generation_job import GenerationJob
from app.models.scene import Scene
from app.models.workflow_template import WorkflowTemplate
from app.services.comfyui_client import ComfyUIClientError, submit_prompt
from app.services.comfyui_events import listen_for_generation
from app.services.workflow_builder import WorkflowBuildError, build_workflow
from app.services.workflow_loader import WorkflowLoadError, load_workflow_template


_logger = get_logger("generation")
_RESERVED_PARAMS = {"prompt", "negative_prompt", "seed"}
_background_tasks: set[asyncio.Task[None]] = set()


class GenerationServiceError(ValueError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _http_status_for_error(code: str) -> int:
    return {
        "COMFYUI_OFFLINE": 503,
        "COMFYUI_TIMEOUT": 504,
        "COMFYUI_SUBMIT_FAILED": 502,
        "COMFYUI_INVALID_RESPONSE": 502,
        "COMFYUI_REQUEST_INVALID": 400,
    }.get(code, 400)


def _start_listener(job_id: str, client_id: str, prompt_id_future: asyncio.Future[str]) -> asyncio.Task[None]:
    task = asyncio.create_task(listen_for_generation(job_id, client_id, prompt_id_future))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def submit_generation(
    db: Session,
    scene: Scene,
    workflow_template: WorkflowTemplate,
    seed: int | None,
    params: dict[str, Any],
) -> GenerationJob:
    reserved = _RESERVED_PARAMS.intersection(params)
    if reserved:
        raise GenerationServiceError("GENERATION_PARAMS_INVALID", "Reserved generation parameter", 400)

    effective_seed = seed if seed is not None else scene.seed
    job = GenerationJob(
        project_id=scene.project_id,
        scene_id=scene.id,
        workflow_template_id=workflow_template.id,
        workflow_version=workflow_template.version,
        prompt_snapshot=scene.prompt or "",
        negative_prompt_snapshot=scene.negative_prompt,
        seed=effective_seed,
        params_json=dict(params),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    _logger.info("Generation job created job_id=%s project_id=%s scene_id=%s", job.id, scene.project_id, scene.id)

    client_id = str(uuid4())
    prompt_id_future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
    listener_task = _start_listener(job.id, client_id, prompt_id_future)
    try:
        loaded = load_workflow_template(workflow_template)
        effective_params = dict(params)
        if "prompt" in loaded.manifest.inputs:
            effective_params["prompt"] = scene.prompt
        if "negative_prompt" in loaded.manifest.inputs:
            effective_params["negative_prompt"] = scene.negative_prompt
        if "seed" in loaded.manifest.inputs and effective_seed is not None:
            effective_params["seed"] = effective_seed
        built_workflow = build_workflow(loaded, effective_params)
        prompt_id = await submit_prompt(built_workflow, client_id=client_id)
    except (WorkflowLoadError, WorkflowBuildError, ComfyUIClientError) as error:
        listener_task.cancel()
        prompt_id_future.cancel()
        job.status = "failed"
        job.error_code = error.code
        job.error_message = str(error)
        job.finished_at = _now()
        db.commit()
        _logger.warning("Generation job failed job_id=%s error_code=%s", job.id, error.code)
        raise GenerationServiceError(error.code, str(error), _http_status_for_error(error.code)) from error

    job.comfy_prompt_id = prompt_id
    job.status = "queued"
    try:
        db.commit()
        db.refresh(job)
    except Exception as error:
        listener_task.cancel()
        prompt_id_future.cancel()
        db.rollback()
        _logger.error("Generation job queue persistence failed job_id=%s", job.id)
        raise GenerationServiceError("GENERATION_PERSISTENCE_FAILED", "Generation job persistence failed", 500) from error

    if not prompt_id_future.done():
        prompt_id_future.set_result(prompt_id)
    _logger.info("Generation job queued job_id=%s comfy_prompt_id=%s", job.id, prompt_id)
    return job
