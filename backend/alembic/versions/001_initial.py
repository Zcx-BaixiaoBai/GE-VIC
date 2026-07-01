"""initial: 3 张核心表 (algorithms / inspections / audit_logs)

Revision ID: 001
Revises:
Create Date: 2026-07-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # algorithms
    op.create_table(
        "algorithms",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64)),
        sa.Column("description", sa.Text),
        sa.Column("engine_type", sa.String(32), nullable=False),
        sa.Column("engine_config", postgresql.JSONB, nullable=False),
        sa.Column("request_schema", postgresql.JSONB),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_algorithms_code", "algorithms", ["code"], unique=True)
    op.create_index("ix_algorithms_category", "algorithms", ["category"])
    op.create_index("ix_algorithms_is_active", "algorithms", ["is_active"])

    # inspections
    op.create_table(
        "inspections",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("algorithm_code", sa.String(64), nullable=False),
        sa.Column("category", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("enrichment_status", sa.String(16)),
        sa.Column("object_key", sa.String(256)),
        sa.Column("file_hash", sa.String(64)),
        sa.Column("file_size", sa.BigInteger),
        sa.Column("file_type", sa.String(16)),
        sa.Column("inspector_id", sa.String(64)),
        sa.Column("asset_id", sa.String(64)),
        sa.Column("location", postgresql.JSONB),
        sa.Column("request_meta", postgresql.JSONB),
        sa.Column("result", postgresql.JSONB),
        sa.Column("summary", sa.Text),
        sa.Column("llm_enrichment", postgresql.JSONB),
        sa.Column("error_message", sa.Text),
        sa.Column("error_code", sa.String(64)),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("cost_estimate", sa.Float),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_inspections_algorithm_code", "inspections", ["algorithm_code"])
    op.create_index("ix_inspections_status", "inspections", ["status"])
    op.create_index("ix_inspections_file_hash", "inspections", ["file_hash"])
    op.create_index("ix_inspections_inspector_id", "inspections", ["inspector_id"])
    op.create_index("ix_inspections_asset_id", "inspections", ["asset_id"])
    op.create_index("ix_inspections_created_at", "inspections", ["created_at"])
    op.create_index("idx_insp_alg_created", "inspections", ["algorithm_code", sa.text("created_at DESC")])
    op.create_index("idx_insp_status_created", "inspections", ["status", sa.text("created_at DESC")])

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(64)),
        sa.Column("source_ip", postgresql.INET),
        sa.Column("user_agent", sa.String(256)),
        sa.Column("request_id", sa.String(64)),
        sa.Column("request_meta", postgresql.JSONB),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.Text),
    )
    op.create_index("ix_audit_logs_occurred_at", "audit_logs", ["occurred_at"])
    op.create_index("idx_audit_actor_time", "audit_logs", ["actor", sa.text("occurred_at DESC")])
    op.create_index("idx_audit_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("idx_audit_action_time", "audit_logs", ["action", sa.text("occurred_at DESC")])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("inspections")
    op.drop_table("algorithms")
