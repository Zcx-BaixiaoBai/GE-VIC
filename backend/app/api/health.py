"""健康检查端点"""
from fastapi import APIRouter

from app import __version__
from app.config import get_settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """健康检查"""
    settings = get_settings()
    return HealthResponse(status="ok", version=__version__, env=settings.app_env)
