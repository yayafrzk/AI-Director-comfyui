import os
import re
from dataclasses import dataclass
from pathlib import Path
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


def asset_directory(project_id: str, asset_type: str) -> Path:
    return get_settings().app_data_dir / "projects" / project_id / _ASSET_DIRECTORIES[asset_type]


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
