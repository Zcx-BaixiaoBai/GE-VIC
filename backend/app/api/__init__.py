"""API routes aggregation"""
from fastapi import APIRouter

from app.api.admin_algorithms import router as admin_algorithms_router
from app.api.algorithms import router as algorithms_router
from app.api.files import router as files_router
from app.api.health import router as health_router
from app.api.inspect import router as inspect_router
from app.api.records import router as records_router
from app.api.settings import router as settings_router
from app.api.tus import router as tus_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(algorithms_router)
api_router.include_router(inspect_router)
api_router.include_router(records_router)
api_router.include_router(files_router)
api_router.include_router(admin_algorithms_router)
api_router.include_router(settings_router)
api_router.include_router(tus_router)

__all__ = ["api_router"]