from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SceneCreate(BaseModel):
    title: str
    description: str | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    seed: int | None = None
    duration_seconds: float
    workflow_template_id: str | None = None


class SceneUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    prompt: str | None = None
    negative_prompt: str | None = None
    seed: int | None = None
    duration_seconds: float | None = None
    workflow_template_id: str | None = None
    status: str | None = None


class SceneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    scene_number: int
    title: str
    description: str | None
    prompt: str | None
    negative_prompt: str | None
    seed: int | None
    duration_seconds: float
    workflow_template_id: str | None
    selected_asset_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime
