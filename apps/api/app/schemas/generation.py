from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class GenerationRequest(BaseModel):
    workflow_template_id: str
    seed: int | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("seed", mode="before")
    @classmethod
    def reject_boolean_seed(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("seed must be an integer")
        return value


class GenerationSubmitRead(BaseModel):
    job_id: str
    status: Literal["queued"]
