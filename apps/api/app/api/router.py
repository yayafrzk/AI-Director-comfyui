from fastapi import APIRouter

from . import assets, comfyui, generation_jobs, health, projects, scenes, workflow_templates


router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(comfyui.router)
router.include_router(projects.router)
router.include_router(scenes.router)
router.include_router(generation_jobs.router)
router.include_router(assets.router)
router.include_router(workflow_templates.router)
