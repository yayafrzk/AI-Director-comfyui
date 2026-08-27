from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.models.scene import Scene
from app.schemas.scene import SceneCreate, SceneRead, SceneUpdate


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
