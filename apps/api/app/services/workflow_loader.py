import json
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.models.workflow_template import WorkflowTemplate
from app.schemas.workflow_manifest import WorkflowManifest


class WorkflowLoadError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class LoadedWorkflowTemplate:
    template: dict[str, Any]
    manifest: WorkflowManifest


def resolve_workflow_path(
    relative_path: str,
    workflow_root: Path | str | None = None,
) -> Path:
    root = Path(workflow_root or get_settings().workflows_dir).expanduser().resolve()
    candidate_path = Path(relative_path)

    if candidate_path.is_absolute() or PureWindowsPath(relative_path).is_absolute():
        raise WorkflowLoadError("WORKFLOW_PATH_INVALID", "Workflow path must be relative")

    resolved_path = (root / candidate_path).resolve()
    try:
        resolved_path.relative_to(root)
    except ValueError as error:
        raise WorkflowLoadError(
            "WORKFLOW_PATH_INVALID",
            "Workflow path escapes workflow root",
        ) from error

    return resolved_path


def _read_json(path: Path) -> Any:
    if not path.is_file():
        raise WorkflowLoadError("WORKFLOW_FILE_NOT_FOUND", "Workflow file was not found")

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        raise WorkflowLoadError("WORKFLOW_FILE_NOT_FOUND", "Workflow file could not be read") from error
    except json.JSONDecodeError as error:
        raise WorkflowLoadError("WORKFLOW_JSON_INVALID", "Workflow JSON is invalid") from error


def _load_template(path: Path) -> dict[str, Any]:
    template = _read_json(path)
    if not isinstance(template, dict):
        raise WorkflowLoadError(
            "WORKFLOW_TEMPLATE_INVALID",
            "Workflow template root must be an object",
        )
    return template


def _load_manifest(path: Path) -> WorkflowManifest:
    raw_manifest = _read_json(path)
    try:
        return WorkflowManifest.model_validate(raw_manifest)
    except ValidationError as error:
        raise WorkflowLoadError(
            "WORKFLOW_MANIFEST_INVALID",
            "Workflow manifest is invalid",
        ) from error


def load_workflow_template(
    workflow_template: WorkflowTemplate,
    workflow_root: Path | str | None = None,
) -> LoadedWorkflowTemplate:
    template_path = resolve_workflow_path(
        workflow_template.template_path,
        workflow_root,
    )
    manifest_path = resolve_workflow_path(
        workflow_template.manifest_path,
        workflow_root,
    )
    template = _load_template(template_path)
    manifest = _load_manifest(manifest_path)

    if (
        manifest.id != workflow_template.slug
        or manifest.version != workflow_template.version
    ):
        raise WorkflowLoadError(
            "WORKFLOW_MANIFEST_MISMATCH",
            "Workflow manifest does not match template metadata",
        )

    return LoadedWorkflowTemplate(template=template, manifest=manifest)
