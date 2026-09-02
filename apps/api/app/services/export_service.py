import json
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.asset import Asset
from app.models.project import Project
from app.models.scene import Scene
from app.services.storage_assets import AssetPathInvalidError, resolve_asset_path


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_SAFE_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,16}\Z")
_MAX_SCENE_TITLE_LENGTH = 80
_MANIFEST_FILENAME = "manifest.json"


class ProjectExportError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ExportedFile:
    scene_id: str
    scene_number: int
    asset_id: str
    filename: str


@dataclass(frozen=True)
class _PlannedFile:
    scene: Scene
    asset: Asset
    source_path: Path
    filename: str


def _safe_scene_title(title: str) -> str:
    safe_title = _INVALID_FILENAME_CHARS.sub("", title).strip().rstrip(". ")
    safe_title = safe_title[:_MAX_SCENE_TITLE_LENGTH].rstrip(". ")
    return safe_title or "scene"


def _export_filename(scene: Scene, source_path: Path) -> str:
    suffix = source_path.suffix
    if suffix and not _SAFE_EXTENSION.fullmatch(suffix):
        raise ProjectExportError("ASSET_PATH_INVALID", "Asset file path is invalid", 409)
    return f"{scene.scene_number:02d}_{_safe_scene_title(scene.title)}{suffix}"


def _export_root(project_id: str) -> Path:
    return get_settings().app_data_dir / "projects" / project_id / "exports"


@dataclass(frozen=True)
class ExportDownload:
    path: Path
    filename: str


def _canonical_export_id(export_id: str) -> str:
    try:
        return str(UUID(export_id))
    except ValueError as error:
        raise ProjectExportError("EXPORT_ID_INVALID", "Export id is invalid", 400) from error


def resolve_export_directory(project_id: str, export_id: str) -> Path:
    canonical_export_id = _canonical_export_id(export_id)
    exports_root = _export_root(project_id).resolve()
    export_directory = (exports_root / canonical_export_id).resolve()
    try:
        export_directory.relative_to(exports_root)
    except ValueError as error:
        raise ProjectExportError("EXPORT_ID_INVALID", "Export id is invalid", 400) from error

    if not export_directory.is_dir():
        raise ProjectExportError("EXPORT_NOT_FOUND", "Export not found", 404)
    return export_directory


def _export_bundle_files(export_directory: Path) -> list[Path]:
    manifest_path = export_directory / _MANIFEST_FILENAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ProjectExportError("EXPORT_CONTENT_INVALID", "Export content is invalid", 409)

    export_root = export_directory.resolve()
    files: list[Path] = []
    for entry in export_directory.iterdir():
        if entry.is_symlink() or not entry.is_file():
            raise ProjectExportError("EXPORT_CONTENT_INVALID", "Export content is invalid", 409)
        try:
            entry.resolve().relative_to(export_root)
        except ValueError as error:
            raise ProjectExportError("EXPORT_CONTENT_INVALID", "Export content is invalid", 409) from error
        files.append(entry)
    return sorted(files, key=lambda entry: entry.name)


def cleanup_export_download(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def prepare_export_download(db: Session, project_id: str, export_id: str) -> ExportDownload:
    if db.get(Project, project_id) is None:
        raise ProjectExportError("PROJECT_NOT_FOUND", "Project not found", 404)

    canonical_export_id = _canonical_export_id(export_id)
    export_directory = resolve_export_directory(project_id, canonical_export_id)
    files = _export_bundle_files(export_directory)
    temporary_directory = get_settings().app_data_dir / "tmp" / "exports"
    temporary_path = temporary_directory / f"{uuid4()}.zip"
    try:
        temporary_directory.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for source in files:
                archive.write(source, arcname=source.name)
    except Exception as error:
        cleanup_export_download(temporary_path)
        raise ProjectExportError("EXPORT_DOWNLOAD_FAILED", "Export download failed", 500) from error

    return ExportDownload(path=temporary_path, filename=f"export-{canonical_export_id}.zip")

def _create_export_directory(project_id: str) -> tuple[str, Path]:
    root = _export_root(project_id)
    try:
        root.mkdir(parents=True, exist_ok=True)
        while True:
            export_id = str(uuid4())
            export_directory = root / export_id
            try:
                export_directory.mkdir()
            except FileExistsError:
                continue
            return export_id, export_directory
    except OSError as error:
        raise ProjectExportError("EXPORT_FAILED", "Project export failed", 500) from error


def _build_manifest(
    project: Project,
    export_id: str,
    created_at: str,
    planned_files: list[_PlannedFile],
) -> dict:
    return {
        "schema_version": 1,
        "project": {
            "id": project.id,
            "name": project.name,
            "aspect_ratio": project.aspect_ratio,
            "width": project.width,
            "height": project.height,
            "fps": project.fps,
        },
        "export": {"export_id": export_id, "created_at": created_at},
        "scenes": [
            {
                "scene_id": planned_file.scene.id,
                "scene_number": planned_file.scene.scene_number,
                "title": planned_file.scene.title,
                "selected_asset_id": planned_file.asset.id,
                "filename": planned_file.filename,
                "asset": {
                    "type": planned_file.asset.type,
                    "mime_type": planned_file.asset.mime_type,
                    "width": planned_file.asset.width,
                    "height": planned_file.asset.height,
                    "duration_seconds": planned_file.asset.duration_seconds,
                    "size_bytes": planned_file.asset.size_bytes,
                },
            }
            for planned_file in planned_files
        ],
    }


def _write_manifest(export_directory: Path, manifest: dict) -> None:
    temporary_path = export_directory / f"{_MANIFEST_FILENAME}.tmp"
    manifest_path = export_directory / _MANIFEST_FILENAME
    with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(temporary_path, manifest_path)

def _plan_export(db: Session, project_id: str) -> tuple[Project, list[_PlannedFile]]:
    project = db.get(Project, project_id)
    if project is None:
        raise ProjectExportError("PROJECT_NOT_FOUND", "Project not found", 404)

    scenes = db.scalars(
        select(Scene)
        .where(Scene.project_id == project_id)
        .order_by(Scene.scene_number.asc())
    ).all()
    planned_files: list[_PlannedFile] = []
    for scene in scenes:
        if scene.selected_asset_id is None:
            raise ProjectExportError(
                "SCENE_SELECTED_ASSET_MISSING",
                "Scene selected asset is missing",
                409,
            )

        asset = db.get(Asset, scene.selected_asset_id)
        if asset is None or asset.project_id != project_id or asset.scene_id != scene.id:
            raise ProjectExportError(
                "SCENE_SELECTED_ASSET_INVALID",
                "Scene selected asset is invalid",
                409,
            )

        try:
            source_path = resolve_asset_path(project_id, asset.relative_path)
        except AssetPathInvalidError as error:
            raise ProjectExportError(
                "ASSET_PATH_INVALID",
                "Asset file path is invalid",
                409,
            ) from error

        if not source_path.is_file():
            raise ProjectExportError(
                "ASSET_FILE_NOT_FOUND",
                "Asset file not found",
                409,
            )

        planned_files.append(
            _PlannedFile(
                scene=scene,
                asset=asset,
                source_path=source_path,
                filename=_export_filename(scene, source_path),
            )
        )
    return project, planned_files


def export_selected_versions(db: Session, project_id: str) -> dict:
    project, planned_files = _plan_export(db, project_id)
    export_id, export_directory = _create_export_directory(project_id)
    try:
        exported_files: list[ExportedFile] = []
        for planned_file in planned_files:
            shutil.copy2(planned_file.source_path, export_directory / planned_file.filename)
            exported_files.append(
                ExportedFile(
                    scene_id=planned_file.scene.id,
                    scene_number=planned_file.scene.scene_number,
                    asset_id=planned_file.asset.id,
                    filename=planned_file.filename,
                )
            )
        manifest = _build_manifest(
            project,
            export_id,
            datetime.now(timezone.utc).isoformat(),
            planned_files,
        )
        _write_manifest(export_directory, manifest)
    except Exception as error:
        shutil.rmtree(export_directory, ignore_errors=True)
        raise ProjectExportError("EXPORT_FAILED", "Project export failed", 500) from error

    return {
        "project_id": project_id,
        "export_id": export_id,
        "export_dir": f"projects/{project_id}/exports/{export_id}",
        "manifest_filename": _MANIFEST_FILENAME,
        "files": [file.__dict__ for file in exported_files],
    }
