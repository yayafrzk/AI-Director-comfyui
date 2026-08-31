import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

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


def _plan_export(db: Session, project_id: str) -> list[_PlannedFile]:
    if db.get(Project, project_id) is None:
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
    return planned_files


def export_selected_versions(db: Session, project_id: str) -> dict:
    planned_files = _plan_export(db, project_id)
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
    except Exception as error:
        shutil.rmtree(export_directory, ignore_errors=True)
        raise ProjectExportError("EXPORT_FAILED", "Project export failed", 500) from error

    return {
        "project_id": project_id,
        "export_id": export_id,
        "export_dir": f"projects/{project_id}/exports/{export_id}",
        "files": [file.__dict__ for file in exported_files],
    }
