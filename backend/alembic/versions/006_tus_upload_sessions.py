"""tus: upload_sessions 表 - TUS 断点续传会话

Revision ID: 006
Revises: 005
Create Date: 2026-07-07

新增:
  - upload_sessions 表, 跟踪 TUS 分片上传会话
  - 状态: uploading / completed / cancelled
  - 24h 过期, 启动时 GC 清理
  - 临时文件存到 upload_tmp_dir 目录
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("total_size", sa.BigInteger, nullable=False),
        sa.Column("offset", sa.BigInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("filename", sa.String(256), nullable=True),
        sa.Column("content_type", sa.String(128), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("tmp_path", sa.String(512), nullable=False),
        sa.Column("file_type", sa.String(16), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'uploading'")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW() + INTERVAL '24 hours'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        comment="TUS upload sessions for resumable uploads",
    )
    op.create_index("ix_upload_sessions_status", "upload_sessions", ["status"])
    op.create_index("ix_upload_sessions_expires_at", "upload_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_upload_sessions_expires_at", table_name="upload_sessions")
    op.drop_index("ix_upload_sessions_status", table_name="upload_sessions")
    op.drop_table("upload_sessions")
