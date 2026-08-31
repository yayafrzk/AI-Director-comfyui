from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.generation import GenerationSubmitRead
from app.schemas.generation_job import GenerationJobRead
from app.services.generation_broadcast import broadcast_generation_event
from app.services.generation_service import (
    GenerationServiceError,
    cancel_generation,
    retry_generation,
)


router = APIRouter(tags=["generation-jobs"])


def _service_error(error: GenerationServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"data": None, "error": {"code": error.code, "message": str(error)}},
    )


@router.post("/generation-jobs/{job_id}/cancel", response_model=None)
async def cancel_generation_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    try:
        job = await cancel_generation(db, job_id)
    except GenerationServiceError as error:
        return _service_error(error)

    await broadcast_generation_event(
        {
            "type": "generation.cancelled",
            "job_id": job.id,
            "scene_id": job.scene_id,
            "status": job.status,
        }
    )
    return {"data": GenerationJobRead.model_validate(job), "error": None}


@router.post("/generation-jobs/{job_id}/retry", response_model=None)
async def retry_generation_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    try:
        job = await retry_generation(db, job_id)
    except GenerationServiceError as error:
        return _service_error(error)
    return {"data": GenerationSubmitRead(job_id=job.id, status="queued"), "error": None}
