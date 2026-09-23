from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workflow_template import WorkflowTemplate


MANUAL_IMPORT_WORKFLOW_SLUG = "__manual_import__"


def get_or_create_manual_import_workflow(db: Session) -> WorkflowTemplate:
    workflow = db.scalar(
        select(WorkflowTemplate).where(
            WorkflowTemplate.slug == MANUAL_IMPORT_WORKFLOW_SLUG
        )
    )
    if workflow is not None:
        return workflow

    workflow = WorkflowTemplate(
        name="Manual Import",
        slug=MANUAL_IMPORT_WORKFLOW_SLUG,
        version="1",
        template_path="__system__/manual-import/template.json",
        manifest_path="__system__/manual-import/manifest.json",
        is_enabled=False,
    )
    db.add(workflow)
    return workflow