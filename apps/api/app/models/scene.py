from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.project import UTCDateTime, _utc_now


class Scene(Base):
    __tablename__ = "scenes"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "scene_number",
            name="uq_scenes_project_scene_number",
        ),
    )

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
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    workflow_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    selected_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=_utc_now,
        onupdate=_utc_now,
        nullable=False,
    )
