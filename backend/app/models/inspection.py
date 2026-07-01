"""识别记录表 - 与 spec §6.2.2 对应"""
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Inspection(Base, TimestampMixin):
    """单次识别的完整记录

    状态机 (主任务):
      PENDING → RUNNING → SUCCESS
                       → FAILED (可重试, 自动重试 ≤ 3 次)
                       → DEAD   (超过 max_retries, 需手动干预)

    LLM 富化 (enrichment_status, 独立流转):
      NONE → ENRICHING → ENRICHED
                     → ENRICH_FAILED (可单独重试)
    """

    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    algorithm_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # 主任务状态
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    enrichment_status: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # 文件
    object_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # 业务元数据
    inspector_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    asset_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    location: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    request_meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # 结果
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    llm_enrichment: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # 错误
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 性能/成本
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 时间
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_insp_alg_created", "algorithm_code", text("created_at DESC")),
        Index("idx_insp_status_created", "status", text("created_at DESC")),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Inspection {self.id} {self.algorithm_code} {self.status}>"
