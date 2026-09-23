from pydantic import BaseModel, field_validator


class OutputInboxSettingsUpdate(BaseModel):
    output_dir: str | None = None


class OutputInboxImportRequest(BaseModel):
    relative_path: str
    prompt_snapshot: str | None = None
    negative_prompt_snapshot: str | None = None
    seed: int | None = None
    select_as_final: bool = False

    @field_validator("seed", mode="before")
    @classmethod
    def reject_boolean_seed(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("seed must be an integer")
        return value
