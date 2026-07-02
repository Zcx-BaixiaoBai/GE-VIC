"""seed: 多模态 LLM 引擎种子算法 (使用 LLM 本身作为识别器)

Revision ID: 004
Revises: 003
Create Date: 2026-07-02

演示模式 (LLM_MOCK_MODE=true) 下, 引擎会返回预设的多模态分析响应, 无需真实 LLM。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO algorithms (
                code, name, category, description, engine_type, engine_config,
                request_schema, is_active, version, created_at, updated_at
            )
            VALUES (
                'multimodal-inspector',
                '多模态巡检分析 [LLM/Multimodal]',
                '通用',
                '用多模态 LLM 直接识别图片/视频内容, 输出设备类型/状态/缺陷的结构化描述。视频自动抽帧 (需 imageio+imageio-ffmpeg)。',
                'multimodal_llm',
                '{"extract_frames": 3, "max_long_edge": 1024, "temperature": 0.3}',
                NULL,
                true,
                1,
                now(),
                now()
            )
            ON CONFLICT (code) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM algorithms WHERE code = 'multimodal-inspector'"))
