from fastapi import APIRouter

from . import health


router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
