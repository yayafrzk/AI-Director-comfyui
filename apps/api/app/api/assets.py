from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import get_db
from app.models.asset import Asset
from app.models.project import Project
from app.models.scene import Scene
from app.schemas.asset import AssetRead, AssetType
from app.services.media_metadata import (
    FFprobeNotFoundError,
    VideoMetadataProbeError,
    probe_video_metadata,
)
from app.services.storage_assets import (
    AssetPathInvalidError,
    cleanup_asset_file,
    create_thumbnail_file,
    resolve_asset_path,
    store_asset_file,
)
from app.services.media_thumbnail import (
    FFmpegNotFoundError,
    VideoThumbnailError,
    generate_video_thumbnail,
)


router = APIRouter(tags=["assets"])
_logger = get_logger("app")


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"data": None, "error": {"code": code, "message": message}},
    )


def _asset_not_found() -> JSONResponse:
    return _error(status.HTTP_404_NOT_FOUND, "ASSET_NOT_FOUND", "Asset not found")


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

    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    stored_thumbnail = None
    if type == "video":
        try:
            metadata = probe_video_metadata(stored_file.path)
        except FFprobeNotFoundError:
            cleanup_asset_file(stored_file.path)
            _logger.error(
                "Video asset upload failed: category=ffprobe_not_found project_id=%s scene_id=%s",
                project_id,
                scene_id,
            )
            return _error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "FFPROBE_NOT_FOUND",
                "ffprobe is not available",
            )
        except VideoMetadataProbeError:
            cleanup_asset_file(stored_file.path)
            _logger.warning(
                "Video asset upload failed: category=metadata_invalid project_id=%s scene_id=%s",
                project_id,
                scene_id,
            )
            return _error(
                status.HTTP_400_BAD_REQUEST,
                "ASSET_MEDIA_INVALID",
                "Unable to read video metadata",
            )
        width = metadata.width
        height = metadata.height
        duration_seconds = metadata.duration_seconds
        try:
            stored_thumbnail = create_thumbnail_file(project_id)
            generate_video_thumbnail(
                stored_file.path,
                stored_thumbnail.path,
                duration_seconds,
            )
        except FFmpegNotFoundError:
            cleanup_asset_file(stored_file.path)
            if stored_thumbnail is not None:
                cleanup_asset_file(stored_thumbnail.path)
            _logger.error(
                "Video asset upload failed: category=ffmpeg_not_found project_id=%s scene_id=%s",
                project_id,
                scene_id,
            )
            return _error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "FFMPEG_NOT_FOUND",
                "ffmpeg is not available",
            )
        except (VideoThumbnailError, OSError):
            cleanup_asset_file(stored_file.path)
            if stored_thumbnail is not None:
                cleanup_asset_file(stored_thumbnail.path)
            _logger.warning(
                "Video asset upload failed: category=thumbnail_failed project_id=%s scene_id=%s",
                project_id,
                scene_id,
            )
            return _error(
                status.HTTP_400_BAD_REQUEST,
                "ASSET_THUMBNAIL_FAILED",
                "Unable to generate video thumbnail",
            )

    asset = Asset(
        project_id=project_id,
        scene_id=scene_id,
        type=type,
        role=role,
        relative_path=stored_file.relative_path,
        thumbnail_path=stored_thumbnail.relative_path if stored_thumbnail is not None else None,
        mime_type=file.content_type or "application/octet-stream",
        width=width,
        height=height,
        duration_seconds=duration_seconds,
        size_bytes=stored_file.size_bytes,
        hash=None,
    )
    db.add(asset)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        cleanup_asset_file(stored_file.path)
        if stored_thumbnail is not None:
            cleanup_asset_file(stored_thumbnail.path)
        return _error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "ASSET_UPLOAD_FAILED",
            "Asset upload failed",
        )

    db.refresh(asset)
    return {"data": AssetRead.model_validate(asset), "error": None}


@router.get("/assets/{asset_id}", response_model=None)
def get_asset(asset_id: str, db: Session = Depends(get_db)) -> dict | JSONResponse:
    asset = db.get(Asset, asset_id)
    if asset is None:
        return _asset_not_found()
    return {"data": AssetRead.model_validate(asset), "error": None}


@router.get("/assets/{asset_id}/content", response_model=None)
def get_asset_content(asset_id: str, db: Session = Depends(get_db)) -> FileResponse | JSONResponse:
    asset = db.get(Asset, asset_id)
    if asset is None:
        return _asset_not_found()

    try:
        file_path = resolve_asset_path(asset.project_id, asset.relative_path)
    except AssetPathInvalidError:
        return _error(status.HTTP_400_BAD_REQUEST, "ASSET_FILE_INVALID", "Asset file path is invalid")

    if not file_path.is_file():
        return _error(status.HTTP_404_NOT_FOUND, "ASSET_FILE_NOT_FOUND", "Asset file not found")

    return FileResponse(file_path, media_type=asset.mime_type or "application/octet-stream")
