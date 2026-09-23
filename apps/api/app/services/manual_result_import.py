from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.generation_job import GenerationJob
from app.models.generation_output import GenerationOutput
from app.models.scene import Scene
from app.services.media_metadata import (
    FFprobeNotFoundError,
    VideoMetadataProbeError,
    probe_video_metadata,
)
from app.services.media_thumbnail import (
    FFmpegNotFoundError,
    VideoThumbnailError,
    generate_video_thumbnail,
)
from app.services.storage_assets import (
    StoredAssetFile,
    StoredThumbnailFile,
    cleanup_asset_file,
    create_thumbnail_file,
    store_asset_file,
)
from app.services.system_workflows import get_or_create_manual_import_workflow


_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}


class ManualResultImportError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _asset_type(upload: UploadFile) -> str:
    content_type = (upload.content_type or "").split(";", 1)[0].lower()
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("video/"):
        return "video"

    suffix = Path(upload.filename or "").suffix.lower()
    if suffix in _IMAGE_EXTENSIONS:
        return "image"
    if suffix in _VIDEO_EXTENSIONS:
        return "video"
    raise ManualResultImportError(
        "MANUAL_RESULT_TYPE_UNSUPPORTED",
        "Only image and video results can be imported",
        400,
    )


def _mime_type(upload: UploadFile, asset_type: str) -> str:
    content_type = (upload.content_type or "").split(";", 1)[0].lower()
    if content_type.startswith(f"{asset_type}/"):
        return content_type
    suffix = Path(upload.filename or "").suffix.lower()
    return f"{asset_type}/{suffix.removeprefix('.')}" if suffix else "application/octet-stream"


def archive_stored_manual_result(
    db: Session,
    scene: Scene,
    stored_file: StoredAssetFile,
    asset_type: str,
    mime_type: str,
    source_params: dict,
    prompt_snapshot: str | None,
    negative_prompt_snapshot: str | None,
    seed: int | None,
    select_as_final: bool,
) -> GenerationJob:
    stored_thumbnail: StoredThumbnailFile | None = None
    committed = False

    try:
        width: int | None = None
        height: int | None = None
        duration_seconds: float | None = None
        if asset_type == "video":
            try:
                metadata = probe_video_metadata(stored_file.path)
            except FFprobeNotFoundError as error:
                raise ManualResultImportError(
                    "FFPROBE_NOT_FOUND", "ffprobe is not available", 503
                ) from error
            except VideoMetadataProbeError as error:
                raise ManualResultImportError(
                    "ASSET_MEDIA_INVALID", "Unable to read video metadata", 400
                ) from error

            width = metadata.width
            height = metadata.height
            duration_seconds = metadata.duration_seconds
            try:
                stored_thumbnail = create_thumbnail_file(scene.project_id)
                generate_video_thumbnail(
                    stored_file.path,
                    stored_thumbnail.path,
                    duration_seconds,
                )
            except FFmpegNotFoundError as error:
                raise ManualResultImportError(
                    "FFMPEG_NOT_FOUND", "ffmpeg is not available", 503
                ) from error
            except (VideoThumbnailError, OSError) as error:
                raise ManualResultImportError(
                    "ASSET_THUMBNAIL_FAILED",
                    "Unable to generate video thumbnail",
                    400,
                ) from error

        workflow = get_or_create_manual_import_workflow(db)
        db.flush()
        asset = Asset(
            project_id=scene.project_id,
            scene_id=scene.id,
            type=asset_type,
            role="output",
            relative_path=stored_file.relative_path,
            thumbnail_path=(
                stored_thumbnail.relative_path if stored_thumbnail is not None else None
            ),
            mime_type=mime_type,
            width=width,
            height=height,
            duration_seconds=duration_seconds,
            size_bytes=stored_file.size_bytes,
            hash=None,
        )
        job = GenerationJob(
            project_id=scene.project_id,
            scene_id=scene.id,
            workflow_template_id=workflow.id,
            workflow_version="manual",
            comfy_prompt_id=None,
            status="completed",
            prompt_snapshot=(scene.prompt or "") if prompt_snapshot is None else prompt_snapshot,
            negative_prompt_snapshot=(
                scene.negative_prompt
                if negative_prompt_snapshot is None
                else negative_prompt_snapshot
            ),
            seed=seed,
            params_json={
                **source_params,
                "duration_seconds": scene.duration_seconds,
                "megapixels": scene.megapixels,
            },
            error_code=None,
            error_message=None,
            started_at=None,
            finished_at=datetime.now(timezone.utc),
        )
        db.add_all([asset, job])
        db.flush()
        db.add(
            GenerationOutput(
                generation_job_id=job.id,
                asset_id=asset.id,
                output_index=0,
            )
        )
        if select_as_final:
            scene.selected_asset_id = asset.id
        db.commit()
        committed = True
        db.refresh(job)
        return job
    except ManualResultImportError:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise ManualResultImportError(
            "MANUAL_RESULT_IMPORT_FAILED",
            "Manual result import failed",
            500,
        ) from error
    finally:
        if not committed:
            cleanup_asset_file(stored_file.path)
            if stored_thumbnail is not None:
                cleanup_asset_file(stored_thumbnail.path)


async def import_manual_result(
    db: Session,
    scene: Scene,
    upload: UploadFile,
    prompt_snapshot: str | None,
    negative_prompt_snapshot: str | None,
    seed: int | None,
    select_as_final: bool,
) -> GenerationJob:
    asset_type = _asset_type(upload)
    try:
        stored_file = await store_asset_file(scene.project_id, asset_type, upload)
    except Exception as error:
        raise ManualResultImportError(
            "MANUAL_RESULT_IMPORT_FAILED",
            "Manual result import failed",
            500,
        ) from error

    return archive_stored_manual_result(
        db,
        scene,
        stored_file,
        asset_type,
        _mime_type(upload, asset_type),
        {"source": "manual_import", "source_filename": Path(upload.filename or "").name},
        prompt_snapshot,
        negative_prompt_snapshot,
        seed,
        select_as_final,
    )
