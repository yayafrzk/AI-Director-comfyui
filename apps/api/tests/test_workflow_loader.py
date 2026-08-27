import json

import pytest

from app.models.workflow_template import WorkflowTemplate
from app.services.workflow_loader import WorkflowLoadError, load_workflow_template


def _workflow_template(**overrides: object) -> WorkflowTemplate:
    values = {
        "name": "Demo workflow",
        "slug": "demo",
        "version": "1.0.0",
        "template_path": "demo/template.json",
        "manifest_path": "demo/manifest.json",
    }
    values.update(overrides)
    return WorkflowTemplate(**values)


def _manifest(**overrides: object) -> dict[str, object]:
    manifest = {
        "id": "demo",
        "name": "一二布布视频工作流",
        "version": "1.0.0",
        "description": "测试中文",
        "inputs": {
            "prompt": {
                "node_id": 12,
                "field": "text",
                "type": "string",
                "required": True,
            }
        },
    }
    manifest.update(overrides)
    return manifest


def _write_json(path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _write_workflow(workflow_root, template: object = None, manifest: object = None) -> None:
    _write_json(
        workflow_root / "demo" / "template.json",
        {"12": {"class_type": "CLIPTextEncode", "inputs": {}}}
        if template is None
        else template,
    )
    _write_json(
        workflow_root / "demo" / "manifest.json",
        _manifest() if manifest is None else manifest,
    )


def _assert_error(code: str, workflow_template: WorkflowTemplate, workflow_root) -> None:
    with pytest.raises(WorkflowLoadError) as error:
        load_workflow_template(workflow_template, workflow_root)
    assert error.value.code == code


def test_load_workflow_template_reads_utf8_template_and_manifest(tmp_path) -> None:
    workflow_root = tmp_path / "workflows"
    _write_workflow(workflow_root)

    loaded = load_workflow_template(_workflow_template(), workflow_root)

    assert loaded.template == {"12": {"class_type": "CLIPTextEncode", "inputs": {}}}
    assert loaded.manifest.name == "一二布布视频工作流"
    assert loaded.manifest.description == "测试中文"
    assert loaded.manifest.inputs["prompt"].node_id == "12"


@pytest.mark.parametrize("path_field", ["template_path", "manifest_path"])
def test_load_workflow_template_rejects_missing_files(tmp_path, path_field: str) -> None:
    workflow_root = tmp_path / "workflows"
    _write_workflow(workflow_root)
    (workflow_root / "demo" / f"{path_field.split('_')[0]}.json").unlink()

    _assert_error(
        "WORKFLOW_FILE_NOT_FOUND",
        _workflow_template(),
        workflow_root,
    )


@pytest.mark.parametrize(
    "relative_path",
    ["../../outside.json", "..\\..\\outside.json", "C:\\outside.json"],
)
def test_load_workflow_template_rejects_unsafe_paths(tmp_path, relative_path: str) -> None:
    workflow_root = tmp_path / "workflows"
    _write_workflow(workflow_root)

    _assert_error(
        "WORKFLOW_PATH_INVALID",
        _workflow_template(template_path=relative_path),
        workflow_root,
    )


@pytest.mark.parametrize("path_name", ["template.json", "manifest.json"])
def test_load_workflow_template_rejects_invalid_json(tmp_path, path_name: str) -> None:
    workflow_root = tmp_path / "workflows"
    _write_workflow(workflow_root)
    (workflow_root / "demo" / path_name).write_text("{ invalid json", encoding="utf-8")

    _assert_error("WORKFLOW_JSON_INVALID", _workflow_template(), workflow_root)


def test_load_workflow_template_rejects_non_object_template(tmp_path) -> None:
    workflow_root = tmp_path / "workflows"
    _write_workflow(workflow_root, template=[])

    _assert_error("WORKFLOW_TEMPLATE_INVALID", _workflow_template(), workflow_root)


@pytest.mark.parametrize(
    "manifest",
    [
        [],
        _manifest(id=None),
        _manifest(name=None),
        _manifest(version=None),
        _manifest(inputs=None),
        _manifest(inputs=[]),
        _manifest(inputs={"prompt": "12"}),
        _manifest(inputs={"prompt": {"field": "text"}}),
        _manifest(inputs={"prompt": {"node_id": "12"}}),
    ],
)
def test_load_workflow_template_rejects_invalid_manifest(tmp_path, manifest: object) -> None:
    workflow_root = tmp_path / "workflows"
    _write_workflow(workflow_root, manifest=manifest)

    _assert_error("WORKFLOW_MANIFEST_INVALID", _workflow_template(), workflow_root)


@pytest.mark.parametrize(
    "manifest",
    [_manifest(id="other"), _manifest(version="2.0.0")],
)
def test_load_workflow_template_rejects_metadata_mismatch(tmp_path, manifest: object) -> None:
    workflow_root = tmp_path / "workflows"
    _write_workflow(workflow_root, manifest=manifest)

    _assert_error("WORKFLOW_MANIFEST_MISMATCH", _workflow_template(), workflow_root)


def test_load_workflow_template_rejects_directory(tmp_path) -> None:
    workflow_root = tmp_path / "workflows"
    _write_workflow(workflow_root)
    (workflow_root / "demo" / "template.json").unlink()
    (workflow_root / "demo" / "template.json").mkdir()

    _assert_error("WORKFLOW_FILE_NOT_FOUND", _workflow_template(), workflow_root)


def test_load_workflow_template_is_independent_of_current_working_directory(tmp_path, monkeypatch) -> None:
    workflow_root = tmp_path / "workflows"
    _write_workflow(workflow_root)
    monkeypatch.chdir(tmp_path)

    loaded = load_workflow_template(_workflow_template(), workflow_root)

    assert loaded.manifest.id == "demo"
