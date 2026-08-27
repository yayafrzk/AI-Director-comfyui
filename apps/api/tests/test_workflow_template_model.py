from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory
from app.models.workflow_template import WorkflowTemplate
from app.schemas.workflow_template import WorkflowTemplateCreate, WorkflowTemplateRead


def _assert_utc(value: datetime) -> None:
    assert value.tzinfo is not None
    assert value.utcoffset() is not None
    assert value.utcoffset().total_seconds() == 0


def _workflow_template(**overrides: object) -> WorkflowTemplate:
    values = {
        "name": "MiniMax H3 I2V",
        "slug": "minimax-h3-i2v",
        "version": "1.0.0",
        "template_path": "minimax-h3-i2v/template.json",
        "manifest_path": "minimax-h3-i2v/manifest.json",
    }
    values.update(overrides)
    return WorkflowTemplate(**values)


def test_workflow_template_orm_round_trip_and_schema_serialization(tmp_path) -> None:
    database_engine = create_engine_for_path(tmp_path / "workflow_template.db")

    try:
        init_db(database_engine)
        assert "workflow_templates" in inspect(database_engine).get_table_names()

        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            workflow_template = _workflow_template()
            session.add(workflow_template)
            session.commit()
            session.refresh(workflow_template)

            assert isinstance(workflow_template.id, str)
            UUID(workflow_template.id)
            assert workflow_template.name == "MiniMax H3 I2V"
            assert workflow_template.slug == "minimax-h3-i2v"
            assert workflow_template.version == "1.0.0"
            assert workflow_template.template_path == "minimax-h3-i2v/template.json"
            assert workflow_template.manifest_path == "minimax-h3-i2v/manifest.json"
            assert workflow_template.is_enabled is True
            _assert_utc(workflow_template.created_at)
            _assert_utc(workflow_template.updated_at)

            loaded_template = session.scalar(
                select(WorkflowTemplate).where(
                    WorkflowTemplate.id == workflow_template.id
                )
            )
            assert loaded_template is not None
            assert loaded_template.template_path == workflow_template.template_path

            read = WorkflowTemplateRead.model_validate(workflow_template)
            assert read.id == workflow_template.id
            assert read.slug == workflow_template.slug
            assert read.created_at == workflow_template.created_at
            assert read.updated_at == workflow_template.updated_at
    finally:
        database_engine.dispose()


def test_workflow_template_allows_disabled_and_nonexistent_paths(tmp_path) -> None:
    database_engine = create_engine_for_path(tmp_path / "workflow_template.db")

    try:
        init_db(database_engine)
        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            workflow_template = _workflow_template(
                slug="disabled-template",
                template_path="missing/template.json",
                manifest_path="missing/manifest.json",
                is_enabled=False,
            )
            session.add(workflow_template)
            session.commit()
            session.refresh(workflow_template)

            assert workflow_template.is_enabled is False
            assert workflow_template.template_path == "missing/template.json"
            assert workflow_template.manifest_path == "missing/manifest.json"
    finally:
        database_engine.dispose()


def test_workflow_template_slug_is_unique(tmp_path) -> None:
    database_engine = create_engine_for_path(tmp_path / "workflow_template.db")

    try:
        init_db(database_engine)
        session_factory = create_session_factory(database_engine)
        with session_factory() as session:
            session.add(_workflow_template())
            session.commit()

            session.add(_workflow_template(name="Second template", version="2.0.0"))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        database_engine.dispose()


def test_workflow_template_create_schema_defaults_and_rejects_blank_fields() -> None:
    create = WorkflowTemplateCreate(
        name="  MiniMax H3 I2V  ",
        slug="  minimax-h3-i2v  ",
        version="  1.0.0  ",
        template_path="  minimax-h3-i2v/template.json  ",
        manifest_path="  minimax-h3-i2v/manifest.json  ",
    )

    assert create.name == "MiniMax H3 I2V"
    assert create.slug == "minimax-h3-i2v"
    assert create.version == "1.0.0"
    assert create.template_path == "minimax-h3-i2v/template.json"
    assert create.manifest_path == "minimax-h3-i2v/manifest.json"
    assert create.is_enabled is True

    valid_values = create.model_dump()
    for field in ("name", "slug", "version", "template_path", "manifest_path"):
        values = valid_values | {field: "   "}
        with pytest.raises(ValidationError):
            WorkflowTemplateCreate(**values)
