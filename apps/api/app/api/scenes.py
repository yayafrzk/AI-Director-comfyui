from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.models.scene import Scene
from app.schemas.scene import SceneCreate, SceneRead


router = APIRouter(prefix="/projects", tags=["scenes"])


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


@router.post("/{project_id}/scenes", status_code=status.HTTP_201_CREATED, response_model=None)
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
