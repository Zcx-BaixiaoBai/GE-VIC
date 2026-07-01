"""审计日志 - 与 spec §6.2.4 对应 (M0 仅 3 表, 含 audit_logs)"""
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """审计日志 - 事后追责

    V1.2 引入, 取代原 chat_* 表。M0 阶段先建表与基础写入服务。
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index("idx_audit_actor_time", "actor", text("occurred_at DESC")),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_action_time", "action", text("occurred_at DESC")),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AuditLog {self.action} {self.resource_type}:{self.resource_id} {self.result}>"
