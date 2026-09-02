from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.export_service import (
    ProjectExportError,
    cleanup_export_download,
    export_selected_versions,
    prepare_export_download,
)


router = APIRouter(prefix="/projects", tags=["projects"])


def _project_not_found() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "data": None,
            "error": {
                "code": "PROJECT_NOT_FOUND",
                "message": "Project not found",
            },
        },
    )


@router.get("")
def list_projects(db: Session = Depends(get_db)) -> dict:
    projects = db.scalars(select(Project).order_by(Project.created_at)).all()
    return {
        "data": [ProjectRead.model_validate(project) for project in projects],
        "error": None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(
    project_create: ProjectCreate,
    db: Session = Depends(get_db),
) -> dict:
    project = Project(**project_create.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"data": ProjectRead.model_validate(project), "error": None}


@router.get("/{project_id}", response_model=None)
def get_project(project_id: str, db: Session = Depends(get_db)) -> dict | JSONResponse:
    project = db.get(Project, project_id)
    if project is None:
        return _project_not_found()
    return {"data": ProjectRead.model_validate(project), "error": None}


@router.patch("/{project_id}", response_model=None)
def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    project = db.get(Project, project_id)
    if project is None:
        return _project_not_found()

    for field, value in project_update.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return {"data": ProjectRead.model_validate(project), "error": None}


@router.delete("/{project_id}", response_model=None)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    project = db.get(Project, project_id)
    if project is None:
        return _project_not_found()

    db.delete(project)
    db.commit()
    return {"data": {"id": project_id}, "error": None}


@router.post("/{project_id}/export", response_model=None)
def export_project_selected_versions(
    project_id: str,
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    try:
        export = export_selected_versions(db, project_id)
    except ProjectExportError as error:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "data": None,
                "error": {"code": error.code, "message": error.message},
            },
        )
    return {"data": export, "error": None}


@router.get("/{project_id}/exports/{export_id}/download", response_model=None)
def download_project_export(
    project_id: str,
    export_id: str,
    db: Session = Depends(get_db),
) -> FileResponse | JSONResponse:
    try:
        download = prepare_export_download(db, project_id, export_id)
    except ProjectExportError as error:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "data": None,
                "error": {"code": error.code, "message": error.message},
            },
        )
    return FileResponse(
        download.path,
        media_type="application/zip",
        filename=download.filename,
        background=BackgroundTask(cleanup_export_download, download.path),
    )
