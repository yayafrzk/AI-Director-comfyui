from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.models.generation_job import GenerationJob
from app.models.workflow_template import WorkflowTemplate
from app.models.scene import Scene
from app.schemas.generation import GenerationRequest, GenerationSubmitRead
from app.schemas.generation_job import GenerationJobRead, GenerationOutputRead
from app.schemas.scene import SceneCreate, SceneRead, SceneReorderRequest, SceneUpdate
from app.services.generation_service import GenerationServiceError, submit_generation


router = APIRouter(tags=["scenes"])


def _project_not_found() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "data": None,
            "error": {
                "code": "PROJECT_NOT_FOUND",
                "message": "Project not found",
            },
        },
    )


def _scene_reorder_invalid(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "data": None,
            "error": {
                "code": "SCENE_REORDER_INVALID",
                "message": message,
            },
        },
    )


def _scene_not_found() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "data": None,
            "error": {
                "code": "SCENE_NOT_FOUND",
                "message": "Scene not found",
            },
        },
    )


@router.post(
    "/projects/{project_id}/scenes",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
)
def create_scene(
    project_id: str,
    scene_create: SceneCreate,
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    if db.get(Project, project_id) is None:
        return _project_not_found()

    current_max = db.scalar(
        select(func.max(Scene.scene_number)).where(Scene.project_id == project_id)
    )
    scene = Scene(
        project_id=project_id,
        scene_number=(current_max or 0) + 1,
        **scene_create.model_dump(),
    )
    db.add(scene)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    db.refresh(scene)
    return {"data": SceneRead.model_validate(scene), "error": None}


@router.get("/projects/{project_id}/scenes", response_model=None)
def list_project_scenes(
    project_id: str,
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    if db.get(Project, project_id) is None:
        return _project_not_found()

    scenes = db.scalars(
        select(Scene)
        .where(Scene.project_id == project_id)
        .order_by(Scene.scene_number)
    ).all()
    return {
        "data": [SceneRead.model_validate(scene) for scene in scenes],
        "error": None,
    }


@router.get("/scenes/{scene_id}", response_model=None)
def get_scene(scene_id: str, db: Session = Depends(get_db)) -> dict | JSONResponse:
    scene = db.get(Scene, scene_id)
    if scene is None:
        return _scene_not_found()
    return {"data": SceneRead.model_validate(scene), "error": None}


@router.patch("/scenes/{scene_id}", response_model=None)
def update_scene(
    scene_id: str,
    scene_update: SceneUpdate,
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    scene = db.get(Scene, scene_id)
    if scene is None:
        return _scene_not_found()

    for field, value in scene_update.model_dump(exclude_unset=True).items():
        setattr(scene, field, value)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    db.refresh(scene)
    return {"data": SceneRead.model_validate(scene), "error": None}


@router.delete("/scenes/{scene_id}", response_model=None)
def delete_scene(scene_id: str, db: Session = Depends(get_db)) -> dict | JSONResponse:
    scene = db.get(Scene, scene_id)
    if scene is None:
        return _scene_not_found()

    db.delete(scene)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return {"data": {"id": scene_id}, "error": None}


@router.post("/projects/{project_id}/scenes/reorder", response_model=None)
def reorder_project_scenes(
    project_id: str,
    reorder_request: SceneReorderRequest,
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    if db.get(Project, project_id) is None:
        return _project_not_found()

    scenes = db.scalars(
        select(Scene)
        .where(Scene.project_id == project_id)
        .order_by(Scene.scene_number)
    ).all()
    scene_ids = reorder_request.scene_ids
    existing_scene_ids = {scene.id for scene in scenes}

    if len(scene_ids) != len(set(scene_ids)):
        return _scene_reorder_invalid("scene_ids must not contain duplicates")
    if set(scene_ids) != existing_scene_ids:
        return _scene_reorder_invalid(
            "scene_ids must contain every Scene in the Project exactly once"
        )

    ordered_scenes = {scene.id: scene for scene in scenes}
    temporary_base = max(
        (scene.scene_number for scene in scenes),
        default=0,
    ) + len(scenes) + 1

    try:
        for index, scene_id in enumerate(scene_ids):
            ordered_scenes[scene_id].scene_number = temporary_base + index
        db.flush()

        for index, scene_id in enumerate(scene_ids, start=1):
            ordered_scenes[scene_id].scene_number = index
        db.flush()
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise

    return {
        "data": [SceneRead.model_validate(ordered_scenes[scene_id]) for scene_id in scene_ids],
        "error": None,
    }

@router.post("/scenes/{scene_id}/generate", response_model=None)
async def generate_scene(
    scene_id: str,
    request: GenerationRequest,
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    scene = db.get(Scene, scene_id)
    if scene is None:
        return _scene_not_found()
    workflow_template = db.get(WorkflowTemplate, request.workflow_template_id)
    if workflow_template is None:
        return JSONResponse(status_code=404, content={"data": None, "error": {"code": "WORKFLOW_TEMPLATE_NOT_FOUND", "message": "Workflow template not found"}})
    if not workflow_template.is_enabled:
        return JSONResponse(status_code=400, content={"data": None, "error": {"code": "WORKFLOW_TEMPLATE_DISABLED", "message": "Workflow template is disabled"}})
    try:
        job = await submit_generation(db, scene, workflow_template, request.seed, request.params)
    except GenerationServiceError as error:
        return JSONResponse(status_code=error.status_code, content={"data": None, "error": {"code": error.code, "message": str(error)}})
    return {"data": GenerationSubmitRead(job_id=job.id, status="queued"), "error": None}
@router.get("/scenes/{scene_id}/generation-jobs", response_model=None)
def list_scene_generation_jobs(scene_id: str, db: Session = Depends(get_db)) -> dict | JSONResponse:
    if db.get(Scene, scene_id) is None:
        return _scene_not_found()
    jobs = db.scalars(
        select(GenerationJob)
        .where(GenerationJob.scene_id == scene_id)
        .order_by(GenerationJob.created_at.desc())
    ).all()
    return {"data": [GenerationJobRead.model_validate(job).model_copy(update={"outputs": [GenerationOutputRead.model_validate(output) for output in sorted(job.outputs, key=lambda output: output.output_index)]}) for job in jobs], "error": None}
