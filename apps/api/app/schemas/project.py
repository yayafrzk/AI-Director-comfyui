from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    aspect_ratio: str
    width: int
    height: int
    fps: int


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    aspect_ratio: str | None = None
    width: int | None = None
    height: int | None = None
    fps: int | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    aspect_ratio: str
    width: int
    height: int
    fps: int
    created_at: datetime
    updated_at: datetime
