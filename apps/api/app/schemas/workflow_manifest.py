from pydantic import BaseModel, ConfigDict, field_validator


class WorkflowManifestInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    node_id: str
    field: str
    type: str | None = None
    required: bool | None = None

    @field_validator("node_id", mode="before")
    @classmethod
    def normalize_node_id(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError("node_id must be a non-empty string or integer")
        return str(value)

    @field_validator("node_id", "field", "type")
    @classmethod
    def validate_non_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("Field must not be blank")
        return cleaned_value


class WorkflowManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    version: str
    inputs: dict[str, WorkflowManifestInput]
    description: str | None = None

    @field_validator("id", "name", "version")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("Field must not be blank")
        return cleaned_value

    @field_validator("inputs")
    @classmethod
    def validate_input_names(
        cls,
        value: dict[str, WorkflowManifestInput],
    ) -> dict[str, WorkflowManifestInput]:
        for input_name in value:
            if not input_name.strip():
                raise ValueError("Input names must not be blank")
        return value
