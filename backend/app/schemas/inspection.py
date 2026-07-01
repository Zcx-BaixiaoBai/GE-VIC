"""识别记录 schema"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InspectionOut(BaseModel):
    """识别记录完整响应 (含识别结果 + LLM 富化 + 元数据)

    对应 spec §7.3.5 自洽响应: 单次调用拿到该图的完整信息
    """
    id: int
    algorithm_code: str
    category: str | None
    status: str
    enrichment_status: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    retry_count: int

    # 业务元数据
    inspector_id: str | None
    asset_id: str | None
    request_meta: dict[str, Any] | None
    location: dict[str, Any] | None

    # 文件
    file: dict[str, Any] | None = Field(
        None, description="{object_key, url, size, hash, type}"
    )

    # 识别结果
    recognition: dict[str, Any] | None
    summary: str | None

    # LLM 富化
    llm_enrichment: dict[str, Any] | None

    # 错误
    error: dict[str, Any] | None = Field(
        None, description="{code, message}"
    )


class InspectionListOut(BaseModel):
    """记录列表响应"""
    items: list[InspectionOut]
    total: int


class InspectionCreateOut(BaseModel):
    """上传成功响应 (202)"""
    record_id: int
    algorithm_code: str
    status: str
    created_at: datetime
    status_url: str


class RetryOut(BaseModel):
    """重试响应"""
    record_id: int
    status: str
    message: str = "重试任务已提交"


class EnrichOut(BaseModel):
    """富化响应"""
    record_id: int
    enrichment_status: str
    message: str = "富化任务已提交"
