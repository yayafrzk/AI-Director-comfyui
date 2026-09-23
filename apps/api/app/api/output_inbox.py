from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.scene import Scene
from app.schemas.generation_job import GenerationJobRead, GenerationOutputRead
from app.schemas.output_inbox import OutputInboxImportRequest, OutputInboxSettingsUpdate
from app.services.output_inbox import (
    OutputInboxError,
    import_output_item,
    list_output_items,
    preview_output_item,
)
from app.services.output_inbox_settings import (
    OutputInboxSettingsError,
    load_output_inbox_settings,
    save_output_inbox_settings,
)


router = APIRouter(tags=["output-inbox"])


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"data": None, "error": {"code": code, "message": message}},
    )


@router.get("/output-inbox/settings", response_model=None)
def get_output_inbox_settings() -> dict | JSONResponse:
    try:
        output_dir = load_output_inbox_settings()
    except (OSError, ValueError):
        return _error(500, "OUTPUT_INBOX_SETTINGS_INVALID", "Output inbox settings could not be read")
    return {"data": {"configured": output_dir is not None, "output_dir": output_dir}, "error": None}


@router.put("/output-inbox/settings", response_model=None)
def put_output_inbox_settings(request: OutputInboxSettingsUpdate) -> dict | JSONResponse:
    try:
        output_dir = save_output_inbox_settings(request.output_dir)
    except OutputInboxSettingsError as error:
        return _error(400, "OUTPUT_INBOX_DIRECTORY_INVALID", str(error))
    except OSError:
        return _error(500, "OUTPUT_INBOX_SETTINGS_FAILED", "Output inbox settings could not be saved")
    return {"data": {"configured": True, "output_dir": output_dir}, "error": None}


@router.get("/output-inbox/items", response_model=None)
def get_output_inbox_items(
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    try:
        items = list_output_items(db, limit)
    except OutputInboxError as error:
        return _error(error.status_code, error.code, str(error))
    return {"data": items, "error": None}


@router.get("/output-inbox/content", response_model=None)
def get_output_inbox_content(path: str) -> FileResponse | JSONResponse:
    try:
        source, mime_type = preview_output_item(path)
    except OutputInboxError as error:
        return _error(error.status_code, error.code, str(error))
    return FileResponse(source, media_type=mime_type)


@router.post("/scenes/{scene_id}/output-inbox/import", response_model=None)
def import_scene_output_item(
    scene_id: str,
    request: OutputInboxImportRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    scene = db.get(Scene, scene_id)
    if scene is None:
        return _error(404, "SCENE_NOT_FOUND", "Scene not found")
    try:
        job = import_output_item(db, scene, request)
    except OutputInboxError as error:
        return _error(error.status_code, error.code, str(error))

    response = GenerationJobRead.model_validate(job).model_copy(
        update={
            "outputs": [
                GenerationOutputRead.model_validate(output)
                for output in sorted(job.outputs, key=lambda output: output.output_index)
            ]
        }
    )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"data": response.model_dump(mode="json"), "error": None},
    )
