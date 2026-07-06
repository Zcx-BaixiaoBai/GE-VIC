"""batch inspection: add batch_files column for joint analysis

Revision ID: 005
Revises: 004
Create Date: 2026-07-03

Adds:
  - inspections.batch_files (JSONB, default '[]') - list of additional files
    for joint (cross-image) analysis. When non-empty, the inspection was
    submitted with multiple files and the engine sees them all together.
  - inspections.is_batch (BOOLEAN, default false) - quick flag for UI/queries
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inspections",
        sa.Column(
            "is_batch",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "inspections",
        sa.Column(
            "batch_files",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_index("ix_inspections_is_batch", "inspections", ["is_batch"])


def downgrade() -> None:
    op.drop_index("ix_inspections_is_batch", table_name="inspections")
    op.drop_column("inspections", "batch_files")
    op.drop_column("inspections", "is_batch")
