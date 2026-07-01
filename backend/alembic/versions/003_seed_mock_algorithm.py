"""seed: 演示算法 (Mock 引擎, 无需真实 API 凭据即可演示 SUCCESS 路径)

Revision ID: 003
Revises: 002
Create Date: 2026-07-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
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
                'insulator-demo',
                '绝缘子破损识别 [Demo/Mock]',
                '供配电',
                '演示用 Mock 引擎, 无需真实阿里云 API 凭据, 直接返回模拟识别结果 + 模拟延迟',
                'mock',
                '{"delay_ms": 500, "defects_count": 1}',
                '{"type": "object", "properties": {"voltage_level": {"type": "string", "enum": ["10kV", "35kV", "110kV", "220kV"]}}}',
                true,
                1,
                now(),
                now()
            )
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM algorithms WHERE code = 'insulator-demo'"))
