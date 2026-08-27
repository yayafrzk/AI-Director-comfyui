from copy import deepcopy
import json
from typing import Any

from app.services.workflow_loader import LoadedWorkflowTemplate


class WorkflowBuildError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _is_json_compatible(value: Any) -> bool:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return False
    return True


def _validate_value(input_type: str | None, value: Any) -> None:
    if value is None:
        raise WorkflowBuildError(
            "WORKFLOW_INPUT_INVALID",
            "Workflow input value must not be null",
        )

    if input_type == "string" and not isinstance(value, str):
        raise WorkflowBuildError("WORKFLOW_INPUT_INVALID", "Workflow input must be a string")
    if input_type == "integer" and (
        isinstance(value, bool) or not isinstance(value, int)
    ):
        raise WorkflowBuildError("WORKFLOW_INPUT_INVALID", "Workflow input must be an integer")
    if input_type == "float" and (
        isinstance(value, bool) or not isinstance(value, (int, float))
    ):
        raise WorkflowBuildError("WORKFLOW_INPUT_INVALID", "Workflow input must be a float")
    if input_type == "boolean" and not isinstance(value, bool):
        raise WorkflowBuildError("WORKFLOW_INPUT_INVALID", "Workflow input must be a boolean")
    if not _is_json_compatible(value):
        raise WorkflowBuildError(
            "WORKFLOW_INPUT_INVALID",
            "Workflow input must be JSON-compatible",
        )


def build_workflow(
    loaded_workflow: LoadedWorkflowTemplate,
    params: dict[str, Any],
) -> dict[str, Any]:
    workflow = deepcopy(loaded_workflow.template)
    manifest_inputs = loaded_workflow.manifest.inputs
    unknown_inputs = set(params) - set(manifest_inputs)
    if unknown_inputs:
        raise WorkflowBuildError("WORKFLOW_INPUT_UNKNOWN", "Unknown workflow input")

    for input_name, mapping in manifest_inputs.items():
        if mapping.required and input_name not in params:
            raise WorkflowBuildError(
                "WORKFLOW_INPUT_REQUIRED",
                "Required workflow input is missing",
            )

        node = workflow.get(mapping.node_id)
        if node is None:
            raise WorkflowBuildError("WORKFLOW_NODE_MISSING", "Workflow node is missing")
        if not isinstance(node, dict):
            raise WorkflowBuildError("WORKFLOW_NODE_INVALID", "Workflow node is invalid")

        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            raise WorkflowBuildError(
                "WORKFLOW_NODE_INVALID",
                "Workflow node inputs are invalid",
            )
        if mapping.field not in inputs:
            raise WorkflowBuildError("WORKFLOW_FIELD_MISSING", "Workflow input field is missing")

        if input_name not in params:
            continue

        value = params[input_name]
        _validate_value(mapping.type, value)
        inputs[mapping.field] = value

    return workflow
