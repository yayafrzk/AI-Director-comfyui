from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.asset import Asset
from app.models.project import Project
from app.models.scene import Scene
from app.schemas.asset import AssetRead, AssetType
from app.services.storage_assets import cleanup_asset_file, store_asset_file


router = APIRouter(tags=["assets"])


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"data": None, "error": {"code": code, "message": message}},
    )


@router.post("/projects/{project_id}/assets/upload", response_model=None)
async def upload_asset(
    project_id: str,
    file: Annotated[UploadFile, File()],
    type: Annotated[AssetType, Form()],
    role: Annotated[str, Form(min_length=1)],
    scene_id: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    if db.get(Project, project_id) is None:
        return _error(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND", "Project not found")

    if scene_id is not None:
        scene = db.get(Scene, scene_id)
        if scene is None:
            return _error(status.HTTP_404_NOT_FOUND, "SCENE_NOT_FOUND", "Scene not found")
        if scene.project_id != project_id:
            return _error(
                status.HTTP_400_BAD_REQUEST,
                "ASSET_SCENE_PROJECT_MISMATCH",
                "Scene does not belong to Project",
            )

    try:
        stored_file = await store_asset_file(project_id, type, file)
    except Exception:
        return _error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "ASSET_UPLOAD_FAILED",
            "Asset upload failed",
        )

    asset = Asset(
        project_id=project_id,
        scene_id=scene_id,
        type=type,
        role=role,
        relative_path=stored_file.relative_path,
        thumbnail_path=None,
        mime_type=file.content_type or "application/octet-stream",
        width=None,
        height=None,
        duration_seconds=None,
        size_bytes=stored_file.size_bytes,
        hash=None,
    )
    db.add(asset)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        cleanup_asset_file(stored_file.path)
        return _error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "ASSET_UPLOAD_FAILED",
            "Asset upload failed",
        )

    db.refresh(asset)
    return {"data": AssetRead.model_validate(asset), "error": None}
