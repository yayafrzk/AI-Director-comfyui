from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class WorkflowTemplateBase(BaseModel):
    name: str
    slug: str
    version: str
    template_path: str
    manifest_path: str
    is_enabled: bool = True

    @field_validator("name", "slug", "version", "template_path", "manifest_path")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("Field must not be blank")
        return cleaned_value


class WorkflowTemplateCreate(WorkflowTemplateBase):
    pass


class WorkflowTemplateRead(WorkflowTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
