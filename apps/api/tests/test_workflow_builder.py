import json
from copy import deepcopy

import pytest

from app.models.workflow_template import WorkflowTemplate
from app.schemas.workflow_manifest import WorkflowManifest
from app.services.workflow_builder import WorkflowBuildError, build_workflow
from app.services.workflow_loader import LoadedWorkflowTemplate, load_workflow_template


def _template() -> dict[str, object]:
    return {
        "12": {"inputs": {"text": "default prompt", "clip": "clip-model"}},
        "45": {"inputs": {"noise_seed": 0}},
        "7": {"inputs": {"image": "default.png"}},
        "60": {"inputs": {"cfg": 5.0}},
        "61": {"inputs": {"enabled": False}},
        "99": {"inputs": {"untouched": "value"}},
    }


def _manifest(**overrides: object) -> WorkflowManifest:
    values = {
        "id": "demo",
        "name": "Demo workflow",
        "version": "1.0.0",
        "inputs": {
            "prompt": {
                "node_id": 12,
                "field": "text",
                "type": "string",
                "required": True,
            },
            "seed": {
                "node_id": "45",
                "field": "noise_seed",
                "type": "integer",
                "required": True,
            },
            "image": {
                "node_id": "7",
                "field": "image",
                "type": "asset",
            },
            "cfg": {
                "node_id": "60",
                "field": "cfg",
                "type": "float",
            },
            "enabled": {
                "node_id": "61",
                "field": "enabled",
                "type": "boolean",
            },
        },
    }
    values.update(overrides)
    return WorkflowManifest.model_validate(values)


def _loaded(template: dict[str, object] | None = None, **manifest_overrides: object) -> LoadedWorkflowTemplate:
    return LoadedWorkflowTemplate(
        template=_template() if template is None else template,
        manifest=_manifest(**manifest_overrides),
    )


def _assert_error(code: str, loaded: LoadedWorkflowTemplate, params: dict[str, object]) -> None:
    with pytest.raises(WorkflowBuildError) as error:
        build_workflow(loaded, params)
    assert error.value.code == code


def test_build_workflow_replaces_only_manifest_mapped_values() -> None:
    loaded = _loaded()
    original_template = deepcopy(loaded.template)

    result = build_workflow(
        loaded,
        {
            "prompt": "一二和布布在湖边散步",
            "seed": 123456,
            "image": "input.png",
            "cfg": 7,
            "enabled": True,
        },
    )

    assert result["12"]["inputs"]["text"] == "一二和布布在湖边散步"
    assert result["45"]["inputs"]["noise_seed"] == 123456
    assert result["7"]["inputs"]["image"] == "input.png"
    assert result["60"]["inputs"]["cfg"] == 7
    assert result["61"]["inputs"]["enabled"] is True
    assert result["12"]["inputs"]["clip"] == "clip-model"
    assert result["99"] == {"inputs": {"untouched": "value"}}
    assert loaded.template == original_template
    assert result is not loaded.template
    assert result["12"] is not loaded.template["12"]
    json.dumps(result)


def test_build_workflow_keeps_optional_defaults_and_isolates_builds() -> None:
    loaded = _loaded()

    result_a = build_workflow(loaded, {"prompt": "A", "seed": 1})
    result_b = build_workflow(loaded, {"prompt": "B", "seed": 2})

    assert result_a["12"]["inputs"]["text"] == "A"
    assert result_a["45"]["inputs"]["noise_seed"] == 1
    assert result_b["12"]["inputs"]["text"] == "B"
    assert result_b["45"]["inputs"]["noise_seed"] == 2
    assert result_a["60"]["inputs"]["cfg"] == 5.0
    assert loaded.template["12"]["inputs"]["text"] == "default prompt"


@pytest.mark.parametrize(
    ("template", "manifest_overrides", "params", "code"),
    [
        ({}, {}, {"prompt": "value", "seed": 1}, "WORKFLOW_NODE_MISSING"),
        ({"12": {}}, {"inputs": {"prompt": {"node_id": "12", "field": "text", "required": True}}}, {"prompt": "value"}, "WORKFLOW_NODE_INVALID"),
        ({"12": {"inputs": []}}, {"inputs": {"prompt": {"node_id": "12", "field": "text", "required": True}}}, {"prompt": "value"}, "WORKFLOW_NODE_INVALID"),
        ({"12": {"inputs": {}}}, {"inputs": {"prompt": {"node_id": "12", "field": "text", "required": True}}}, {"prompt": "value"}, "WORKFLOW_FIELD_MISSING"),
    ],
)
def test_build_workflow_rejects_invalid_mappings(template, manifest_overrides, params, code) -> None:
    _assert_error(code, _loaded(template=template, **manifest_overrides), params)


def test_build_workflow_rejects_missing_required_and_unknown_inputs() -> None:
    loaded = _loaded()

    _assert_error("WORKFLOW_INPUT_REQUIRED", loaded, {"seed": 1})
    _assert_error(
        "WORKFLOW_INPUT_UNKNOWN",
        loaded,
        {"prompt": "value", "seed": 1, "sead": 2},
    )


@pytest.mark.parametrize(
    ("input_name", "value"),
    [
        ("prompt", 1),
        ("seed", True),
        ("cfg", True),
        ("enabled", "true"),
        ("image", None),
        ("image", object()),
    ],
)
def test_build_workflow_rejects_invalid_input_values(input_name: str, value: object) -> None:
    params = {"prompt": "value", "seed": 1, input_name: value}
    _assert_error("WORKFLOW_INPUT_INVALID", _loaded(), params)


def test_build_workflow_integrates_with_loader(tmp_path) -> None:
    workflow_root = tmp_path / "workflows"
    workflow_directory = workflow_root / "demo"
    workflow_directory.mkdir(parents=True)
    (workflow_directory / "template.json").write_text(
        json.dumps(_template()),
        encoding="utf-8",
    )
    (workflow_directory / "manifest.json").write_text(
        json.dumps(_manifest().model_dump()),
        encoding="utf-8",
    )
    workflow_template = WorkflowTemplate(
        name="Demo workflow",
        slug="demo",
        version="1.0.0",
        template_path="demo/template.json",
        manifest_path="demo/manifest.json",
    )

    loaded = load_workflow_template(workflow_template, workflow_root)
    result = build_workflow(loaded, {"prompt": "集成测试", "seed": 9})

    assert result["12"]["inputs"]["text"] == "集成测试"
    assert result["45"]["inputs"]["noise_seed"] == 9
