from fastapi import APIRouter

from . import health, projects, scenes


router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(projects.router)
router.include_router(scenes.router)
