"""TUS 断点续传会话表 - 用于跟踪分片上传的临时会话

字段:
  - id (UUID, 客户端生成): 会话标识, 用在 URL 里
  - total_size: 文件总字节数 (Upload-Length)
  - offset: 已写入字节数 (Upload-Offset)
  - filename / content_type: 客户端提供的元数据
  - metadata: 客户端 TUS 扩展元数据 (algorithm_code, inspector_id, file_hash 等)
  - tmp_path: 后端临时文件路径 (相对 upload_tmp_dir)
  - status: pending / completed / cancelled
  - completed_at / expires_at: 过期清理用
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


def _new_session_id() -> str:
    """生成 URL 安全的 session id (32 字符)"""
    return uuid.uuid4().hex


class UploadSession(Base, TimestampMixin):
    """TUS 断点续传会话 - 临时表, 完成后或过期后清理"""

    __tablename__ = "upload_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_session_id)

    # TUS 协议字段
    total_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    offset: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default=text("0"))
    filename: Mapped[str | None] = mapped_column(String(256), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # TUS 扩展元数据: algorithm_code, inspector_id, file_hash, asset_id 等
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # 后端临时存储
    tmp_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # image / video / other

    # 状态机
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="uploading", server_default=text("'uploading'"), index=True)

    # 过期时间 - 24h 后视为过期, 由启动时 GC 清理
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=text("NOW() + INTERVAL '24 hours'"),
    )

    __table_args__ = (
        # 索引: 快速找过期会话
        {"comment": "TUS upload sessions for resumable uploads"},
    )
