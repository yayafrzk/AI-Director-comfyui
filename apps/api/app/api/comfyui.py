from fastapi import APIRouter

from app.services.comfyui_client import check_health


router = APIRouter(prefix="/comfyui", tags=["comfyui"])


@router.get("/health")
async def health() -> dict[str, object]:
    result = await check_health()
    return {
        "data": result.model_dump(),
        "error": None,
    }
