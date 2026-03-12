"""structured metrics table

Revision ID: 20260311_0003
Revises: 20260311_0002
Create Date: 2026-03-11 00:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260311_0003"
down_revision = "20260311_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "structured_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pitch_id", sa.String(length=128), nullable=False),
        sa.Column("metric_key", sa.String(length=128), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("source_table", sa.String(length=128), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_structured_metrics_pitch_metric",
        "structured_metrics",
        ["pitch_id", "metric_key"],
        unique=True,
    )
    op.create_index(
        "ix_structured_metrics_pitch_id",
        "structured_metrics",
        ["pitch_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_structured_metrics_pitch_id", table_name="structured_metrics")
    op.drop_index("ix_structured_metrics_pitch_metric", table_name="structured_metrics")
    op.drop_table("structured_metrics")
