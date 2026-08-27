import os
import re
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings


_ASSET_DIRECTORIES = {
    "image": "images",
    "video": "videos",
    "audio": "audio",
    "reference": "source",
}
_CHUNK_SIZE = 1024 * 1024
_SAFE_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,16}\Z")


@dataclass(frozen=True)
class StoredAssetFile:
    relative_path: str
    path: Path
    size_bytes: int


@dataclass(frozen=True)
class StoredThumbnailFile:
    relative_path: str
    path: Path


class AssetPathInvalidError(ValueError):
    pass


def asset_directory(project_id: str, asset_type: str) -> Path:
    return get_settings().app_data_dir / "projects" / project_id / _ASSET_DIRECTORIES[asset_type]


def create_thumbnail_file(project_id: str) -> StoredThumbnailFile:
    directory = get_settings().app_data_dir / "projects" / project_id / "thumbnails"
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.jpg"
    return StoredThumbnailFile(
        relative_path=f"thumbnails/{filename}",
        path=directory / filename,
    )


def resolve_asset_path(project_id: str, relative_path: str) -> Path:
    project_root = (get_settings().app_data_dir / "projects" / project_id).resolve()
    candidate_path = Path(relative_path)

    if candidate_path.is_absolute() or PureWindowsPath(relative_path).is_absolute():
        raise AssetPathInvalidError("Asset path must be relative")

    resolved_path = (project_root / candidate_path).resolve()
    try:
        resolved_path.relative_to(project_root)
    except ValueError as error:
        raise AssetPathInvalidError("Asset path escapes project root") from error

    return resolved_path


def _safe_extension(filename: str | None) -> str:
    suffix = Path(filename or "").name
    suffix = Path(suffix).suffix.lower()
    return suffix if _SAFE_EXTENSION.fullmatch(suffix) else ""


async def store_asset_file(project_id: str, asset_type: str, upload: UploadFile) -> StoredAssetFile:
    directory_name = _ASSET_DIRECTORIES[asset_type]
    target_directory = asset_directory(project_id, asset_type)
    target_directory.mkdir(parents=True, exist_ok=True)

    file_token = uuid4().hex
    final_name = f"{file_token}{_safe_extension(upload.filename)}"
    temporary_path = target_directory / f"{file_token}.tmp"
    final_path = target_directory / final_name
    size_bytes = 0

    try:
        with temporary_path.open("wb") as destination:
            while chunk := await upload.read(_CHUNK_SIZE):
                destination.write(chunk)
                size_bytes += len(chunk)
        os.replace(temporary_path, final_path)
    except Exception:
        cleanup_asset_file(temporary_path)
        cleanup_asset_file(final_path)
        raise

    return StoredAssetFile(
        relative_path=f"{directory_name}/{final_name}",
        path=final_path,
        size_bytes=size_bytes,
    )


def cleanup_asset_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
