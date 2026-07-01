"""API 路由聚合"""
from fastapi import APIRouter

from app.api.algorithms import router as algorithms_router
from app.api.files import router as files_router
from app.api.health import router as health_router
from app.api.inspect import router as inspect_router
from app.api.records import router as records_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(algorithms_router)
api_router.include_router(inspect_router)
api_router.include_router(records_router)
api_router.include_router(files_router)

__all__ = ["api_router"]
