"""seed: 种子算法数据 - 绝缘子破损识别

Revision ID: 002
Revises: 001
Create Date: 2026-07-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
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
                'insulator-damage',
                '绝缘子破损识别',
                '供配电',
                '识别绝缘子伞裙破损、污秽、闪络等缺陷',
                'cloud_api',
                '{"provider": "aliyun", "endpoint": "https://imagerecog.cn-shanghai.aliyuncs.com", "action": "RecognizeInsulatorDamage", "access_key_id": "REPLACE_ME", "access_key_secret": "REPLACE_ME"}',
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
    op.execute(sa.text("DELETE FROM algorithms WHERE code = 'insulator-damage'"))
