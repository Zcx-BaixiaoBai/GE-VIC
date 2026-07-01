"""算法 schema"""
from typing import Any

from pydantic import BaseModel, Field


class AlgorithmOut(BaseModel):
    """单条算法响应"""
    code: str
    name: str
    category: str | None
    description: str | None
    engine_type: str
    is_active: bool
    version: int
    engine_config: dict[str, Any] = Field(default_factory=dict)
    request_schema: dict[str, Any] | None = None


class AlgorithmListOut(BaseModel):
    """算法列表响应"""
    items: list[AlgorithmOut]
    total: int
