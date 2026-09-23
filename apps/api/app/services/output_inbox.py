import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.generation_job import GenerationJob
from app.models.scene import Scene
from app.schemas.output_inbox import OutputInboxImportRequest
from app.services.manual_result_import import (
    ManualResultImportError,
    archive_stored_manual_result,
)
from app.services.storage_assets import cleanup_asset_file, store_asset_path
from app.services.output_inbox_settings import (
    OutputInboxSettingsError,
    load_output_inbox_settings,
    validate_output_directory,
)


_MIME_TYPES = {
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".png": ("image", "image/png"),
    ".webp": ("image", "image/webp"),
    ".mp4": ("video", "video/mp4"),
    ".mov": ("video", "video/quicktime"),
    ".webm": ("video", "video/webm"),
}


class OutputInboxError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def configured_root() -> Path:
    try:
        output_dir = load_output_inbox_settings()
    except (OSError, ValueError) as error:
        raise OutputInboxError("OUTPUT_INBOX_DIRECTORY_INVALID", "Output directory is invalid", 400) from error
    if output_dir is None:
        raise OutputInboxError("OUTPUT_INBOX_NOT_CONFIGURED", "Output directory is not configured", 400)
    try:
        return validate_output_directory(output_dir)
    except OutputInboxSettingsError as error:
        raise OutputInboxError("OUTPUT_INBOX_DIRECTORY_INVALID", "Output directory is invalid", 400) from error


def supported_media(path: Path) -> tuple[str, str]:
    media = _MIME_TYPES.get(path.suffix.lower())
    if media is None:
        raise OutputInboxError("OUTPUT_INBOX_TYPE_UNSUPPORTED", "Output file type is not supported", 400)
    return media


def resolve_output_path(root: Path, relative_path: str) -> Path:
    if not relative_path or "\x00" in relative_path:
        raise OutputInboxError("OUTPUT_INBOX_PATH_INVALID", "Output path is invalid", 400)
    windows_path = PureWindowsPath(relative_path)
    posix_path = PurePosixPath(relative_path)
    if (
        Path(relative_path).is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or posix_path.is_absolute()
        or ".." in windows_path.parts
        or ".." in posix_path.parts
    ):
        raise OutputInboxError("OUTPUT_INBOX_PATH_INVALID", "Output path is invalid", 400)

    candidate = root / relative_path
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (ValueError, OSError, RuntimeError) as error:
        raise OutputInboxError("OUTPUT_INBOX_PATH_INVALID", "Output path is invalid", 400) from error
    if not resolved.is_file():
        raise OutputInboxError("OUTPUT_INBOX_ITEM_NOT_FOUND", "Output file was not found", 404)
    return resolved


def item_identity(relative_path: str, size_bytes: int, mtime_ns: int) -> str:
    key = f"{relative_path}|{size_bytes}|{mtime_ns}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _archived_scenes(db: Session) -> dict[str, str]:
    jobs = db.scalars(
        select(GenerationJob)
        .where(GenerationJob.status == "completed")
        .order_by(GenerationJob.created_at.desc(), GenerationJob.id.desc())
    ).all()
    archived: dict[str, str] = {}
    for job in jobs:
        params = job.params_json or {}
        if params.get("source") != "comfyui_output_inbox":
            continue
        source_id = params.get("source_inbox_id")
        if isinstance(source_id, str) and source_id not in archived:
            archived[source_id] = job.scene_id
    return archived


def archived_scene_id(db: Session, source_id: str) -> str | None:
    return _archived_scenes(db).get(source_id)


def list_output_items(db: Session, limit: int) -> list[dict]:
    root = configured_root()
    archived = _archived_scenes(db)
    items: list[dict] = []
    try:
        paths = root.rglob("*")
        for path in paths:
            if path.suffix.lower() not in _MIME_TYPES:
                continue
            try:
                resolved = path.resolve()
                resolved.relative_to(root)
                if not resolved.is_file():
                    continue
                stat = resolved.stat()
            except (OSError, ValueError, RuntimeError):
                continue
            relative_path = path.relative_to(root).as_posix()
            source_id = item_identity(relative_path, stat.st_size, stat.st_mtime_ns)
            scene_id = archived.get(source_id)
            items.append(
                {
                    "id": source_id,
                    "relative_path": relative_path,
                    "filename": path.name,
                    "type": _MIME_TYPES[path.suffix.lower()][0],
                    "size_bytes": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    "archived": scene_id is not None,
                    "archived_scene_id": scene_id,
                }
            )
    except OSError as error:
        raise OutputInboxError("OUTPUT_INBOX_DIRECTORY_INVALID", "Output directory cannot be read", 400) from error
    items.sort(key=lambda item: (-item["mtime_ns"], item["relative_path"]))
    for item in items:
        del item["mtime_ns"]
    return items[:limit]


def preview_output_item(relative_path: str) -> tuple[Path, str]:
    root = configured_root()
    source = resolve_output_path(root, relative_path)
    _media_type, mime_type = supported_media(source)
    return source, mimetypes.guess_type(source.name)[0] or mime_type


def import_output_item(
    db: Session,
    scene: Scene,
    request: OutputInboxImportRequest,
) -> GenerationJob:
    root = configured_root()
    source = resolve_output_path(root, request.relative_path)
    asset_type, mime_type = supported_media(source)
    relative_path = Path(request.relative_path).as_posix()
    try:
        stat = source.stat()
    except OSError as error:
        raise OutputInboxError("OUTPUT_INBOX_ITEM_NOT_FOUND", "Output file was not found", 404) from error

    source_id = item_identity(relative_path, stat.st_size, stat.st_mtime_ns)
    if archived_scene_id(db, source_id) is not None:
        raise OutputInboxError(
            "OUTPUT_INBOX_ITEM_ALREADY_ARCHIVED", "Output file is already archived", 409
        )
    if datetime.now(timezone.utc).timestamp() - stat.st_mtime < 2:
        raise OutputInboxError(
            "OUTPUT_INBOX_ITEM_BUSY", "Output file may still be being written", 409
        )

    try:
        stored_file = store_asset_path(scene.project_id, asset_type, source, source.name)
    except OSError as error:
        raise OutputInboxError("OUTPUT_INBOX_IMPORT_FAILED", "Output file could not be copied", 500) from error

    try:
        current = source.stat()
    except OSError:
        cleanup_asset_file(stored_file.path)
        raise OutputInboxError("OUTPUT_INBOX_ITEM_BUSY", "Output file changed during import", 409)
    if (current.st_size, current.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
        cleanup_asset_file(stored_file.path)
        raise OutputInboxError("OUTPUT_INBOX_ITEM_BUSY", "Output file changed during import", 409)

    try:
        return archive_stored_manual_result(
            db,
            scene,
            stored_file,
            asset_type,
            mime_type,
            {
                "source": "comfyui_output_inbox",
                "source_filename": source.name,
                "source_relative_path": relative_path,
                "source_inbox_id": source_id,
                "source_size_bytes": stat.st_size,
                "source_mtime_ns": stat.st_mtime_ns,
            },
            request.prompt_snapshot,
            request.negative_prompt_snapshot,
            request.seed,
            request.select_as_final,
        )
    except ManualResultImportError as error:
        raise OutputInboxError(error.code, str(error), error.status_code) from error
