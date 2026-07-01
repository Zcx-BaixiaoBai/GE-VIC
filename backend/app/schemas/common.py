"""通用 schema"""
from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """统一错误响应"""
    code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    details: dict[str, Any] | None = Field(None, description="额外上下文")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    version: str
    env: str
