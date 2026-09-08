from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.workflow_template import WorkflowTemplate
from app.schemas.workflow_template import WorkflowTemplateCreate, WorkflowTemplateRead
from app.services.workflow_loader import WorkflowLoadError, load_workflow_template

router = APIRouter(tags=["workflow-templates"])


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"data": None, "error": {"code": code, "message": message}})


@router.get("/workflow-templates", response_model=None)
def list_workflow_templates(db: Session = Depends(get_db)) -> dict:
    templates = db.scalars(select(WorkflowTemplate).order_by(WorkflowTemplate.created_at.asc(), WorkflowTemplate.id.asc())).all()
    return {"data": [WorkflowTemplateRead.model_validate(item) for item in templates], "error": None}


@router.get("/workflow-templates/{workflow_template_id}", response_model=None)
def get_workflow_template(workflow_template_id: str, db: Session = Depends(get_db)) -> dict | JSONResponse:
    template = db.get(WorkflowTemplate, workflow_template_id)
    if template is None:
        return _error(status.HTTP_404_NOT_FOUND, "WORKFLOW_TEMPLATE_NOT_FOUND", "Workflow template not found")
    return {"data": WorkflowTemplateRead.model_validate(template), "error": None}


@router.post("/workflow-templates/import", response_model=None)
def import_workflow_template(payload: WorkflowTemplateCreate, db: Session = Depends(get_db)) -> dict | JSONResponse:
    if db.scalar(select(WorkflowTemplate.id).where(WorkflowTemplate.slug == payload.slug)) is not None:
        return _error(status.HTTP_409_CONFLICT, "WORKFLOW_TEMPLATE_SLUG_EXISTS", "Workflow template slug already exists")
    template = WorkflowTemplate(**payload.model_dump())
    try:
        load_workflow_template(template)
    except WorkflowLoadError as error:
        code = error.code
        return _error(status.HTTP_404_NOT_FOUND if code == "WORKFLOW_FILE_NOT_FOUND" else status.HTTP_400_BAD_REQUEST, code, str(error))
    db.add(template)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.scalar(select(WorkflowTemplate.id).where(WorkflowTemplate.slug == payload.slug)) is not None:
            return _error(status.HTTP_409_CONFLICT, 'WORKFLOW_TEMPLATE_SLUG_EXISTS', 'Workflow template slug already exists')
        return _error(status.HTTP_500_INTERNAL_SERVER_ERROR, 'WORKFLOW_TEMPLATE_IMPORT_FAILED', 'Workflow template import failed')
    except SQLAlchemyError:
        db.rollback()
        return _error(status.HTTP_500_INTERNAL_SERVER_ERROR, "WORKFLOW_TEMPLATE_IMPORT_FAILED", "Workflow template import failed")
    db.refresh(template)
    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"data": WorkflowTemplateRead.model_validate(template).model_dump(mode="json"), "error": None})
