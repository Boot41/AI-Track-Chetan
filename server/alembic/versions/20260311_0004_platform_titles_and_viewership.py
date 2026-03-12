"""platform titles and historical viewership metrics

Revision ID: 20260311_0004
Revises: 20260311_0003
Create Date: 2026-03-11 01:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260311_0004"
down_revision = "20260311_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_titles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title_key", sa.String(length=128), nullable=False),
        sa.Column("title_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("primary_genre", sa.String(length=64), nullable=False),
        sa.Column("secondary_genre", sa.String(length=64), nullable=True),
        sa.Column("release_year", sa.Integer(), nullable=True),
        sa.Column("origin_region", sa.String(length=64), nullable=True),
        sa.Column("is_top_title", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_platform_titles_title_key", "platform_titles", ["title_key"], unique=True)
    op.create_index(
        "ix_platform_titles_primary_genre",
        "platform_titles",
        ["primary_genre"],
        unique=False,
    )
    op.create_index(
        "ix_platform_titles_secondary_genre",
        "platform_titles",
        ["secondary_genre"],
        unique=False,
    )
    op.create_index(
        "ix_platform_titles_is_top_title",
        "platform_titles",
        ["is_top_title"],
        unique=False,
    )

    op.create_table(
        "historical_viewership_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title_id", sa.Integer(), sa.ForeignKey("platform_titles.id"), nullable=False),
        sa.Column("market", sa.String(length=32), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.Column("completion_rate", sa.Float(), nullable=False),
        sa.Column("dropoff_rate", sa.Float(), nullable=False),
        sa.Column("retention_lift", sa.Float(), nullable=False),
        sa.Column("cost_per_view", sa.Float(), nullable=False),
        sa.Column("roi", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_historical_viewership_metrics_title_id",
        "historical_viewership_metrics",
        ["title_id"],
        unique=False,
    )
    op.create_index(
        "ix_historical_viewership_metrics_market",
        "historical_viewership_metrics",
        ["market"],
        unique=False,
    )
    op.create_index(
        "ix_historical_viewership_metrics_metric_date",
        "historical_viewership_metrics",
        ["metric_date"],
        unique=False,
    )
    op.create_index(
        "ix_historical_viewership_metrics_title_market_date",
        "historical_viewership_metrics",
        ["title_id", "market", "metric_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_historical_viewership_metrics_title_market_date",
        table_name="historical_viewership_metrics",
    )
    op.drop_index(
        "ix_historical_viewership_metrics_metric_date",
        table_name="historical_viewership_metrics",
    )
    op.drop_index(
        "ix_historical_viewership_metrics_market",
        table_name="historical_viewership_metrics",
    )
    op.drop_index(
        "ix_historical_viewership_metrics_title_id",
        table_name="historical_viewership_metrics",
    )
    op.drop_table("historical_viewership_metrics")

    op.drop_index("ix_platform_titles_is_top_title", table_name="platform_titles")
    op.drop_index("ix_platform_titles_secondary_genre", table_name="platform_titles")
    op.drop_index("ix_platform_titles_primary_genre", table_name="platform_titles")
    op.drop_index("ix_platform_titles_title_key", table_name="platform_titles")
    op.drop_table("platform_titles")
