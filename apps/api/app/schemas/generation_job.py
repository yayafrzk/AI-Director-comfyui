from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


GenerationJobStatus = Literal[
    "pending",
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]


class GenerationJobBase(BaseModel):
    workflow_version: str
    prompt_snapshot: str
    negative_prompt_snapshot: str | None = None
    seed: int | None = None
    params_json: dict[str, Any] = Field(default_factory=dict)
    status: GenerationJobStatus = "pending"

    @field_validator("workflow_version")
    @classmethod
    def validate_workflow_version(cls, value: str) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("workflow_version must not be blank")
        return cleaned_value

    @field_validator("seed", mode="before")
    @classmethod
    def reject_boolean_seed(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("seed must be an integer")
        return value


class GenerationJobCreate(GenerationJobBase):
    project_id: str
    scene_id: str
    workflow_template_id: str


class GenerationOutputAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    type: str
    role: str
    thumbnail_path: str | None
    mime_type: str
    relative_path: str
    width: int | None
    height: int | None
    duration_seconds: float | None
    created_at: datetime


class GenerationOutputRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    output_index: int
    asset: GenerationOutputAssetRead


class GenerationJobRead(GenerationJobBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    scene_id: str
    workflow_template_id: str
    comfy_prompt_id: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    outputs: list[GenerationOutputRead] = Field(default_factory=list)
