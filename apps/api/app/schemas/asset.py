from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AssetType = Literal["image", "video", "audio", "reference"]


class AssetBase(BaseModel):
    type: AssetType
    role: str
    relative_path: str = Field(min_length=1)
    thumbnail_path: str | None = None
    mime_type: str = Field(min_length=1)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    size_bytes: int = Field(ge=0)
    hash: str | None = None


class AssetCreate(AssetBase):
    project_id: str
    scene_id: str | None = None


class AssetRead(AssetBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    scene_id: str | None
    created_at: datetime
