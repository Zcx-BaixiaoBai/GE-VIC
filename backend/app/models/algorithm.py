"""算法注册表 - 与 spec §6.2.1 对应"""
from typing import Any

from sqlalchemy import BigInteger, Boolean, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Algorithm(Base, TimestampMixin):
    """算法注册表

    一行代表一种识别能力。新增算法 = INSERT 一行配置。
    业务代码与 API 路由无需变更。
    """

    __tablename__ = "algorithms"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    engine_type: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    request_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Algorithm {self.code} ({self.engine_type})>"
