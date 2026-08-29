from datetime import datetime
from typing import Any, TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import BigInteger, JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.project import UTCDateTime, _utc_now

if TYPE_CHECKING:
    from app.models.generation_output import GenerationOutput


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id"),
        nullable=False,
    )
    scene_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("scenes.id"),
        nullable=False,
    )
    workflow_template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_templates.id"),
        nullable=False,
    )
    workflow_version: Mapped[str] = mapped_column(String, nullable=False)
    comfy_prompt_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    prompt_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    params_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    outputs: Mapped[list["GenerationOutput"]] = relationship(back_populates="job")

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_utc_now,
        nullable=False,
    )
