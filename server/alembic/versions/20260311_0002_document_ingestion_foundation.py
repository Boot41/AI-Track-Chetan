"""document ingestion foundation

Revision ID: 20260311_0002
Revises: 20260310_0001
Create Date: 2026-03-11 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.db.vector_type import PGVECTOR_AVAILABLE, Vector

revision = "20260311_0002"
down_revision = "20260310_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if PGVECTOR_AVAILABLE:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column("documents", sa.Column("content_id", sa.String(length=128), nullable=True))
    op.add_column("documents", sa.Column("pitch_id", sa.String(length=128), nullable=True))
    op.add_column("documents", sa.Column("filename", sa.String(length=255), nullable=True))
    op.add_column("documents", sa.Column("parser_used", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("sectioning_hint", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("warnings_json", sa.JSON(), nullable=True))
    op.add_column("documents", sa.Column("errors_json", sa.JSON(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "fallback_applied",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index("ix_documents_content_id", "documents", ["content_id"], unique=False)
    op.create_index("ix_documents_pitch_id", "documents", ["pitch_id"], unique=False)

    op.add_column(
        "document_sections",
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "document_sections",
        sa.Column("source_reference", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "document_sections",
        sa.Column(
            "structure_confidence",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
    )
    op.add_column("document_sections", sa.Column("embedding_model", sa.String(length=128)))
    op.add_column("document_sections", sa.Column("embedding", Vector(12), nullable=True))
    op.create_index(
        "ix_document_sections_source_reference",
        "document_sections",
        ["source_reference"],
        unique=False,
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_sections_fts
        ON document_sections
        USING gin (to_tsvector('english', coalesce(title, '') || ' ' || content))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_sections_fts")
    op.drop_index("ix_document_sections_source_reference", table_name="document_sections")
    op.drop_column("document_sections", "embedding")
    op.drop_column("document_sections", "embedding_model")
    op.drop_column("document_sections", "structure_confidence")
    op.drop_column("document_sections", "source_reference")
    op.drop_column("document_sections", "order_index")

    op.drop_index("ix_documents_pitch_id", table_name="documents")
    op.drop_index("ix_documents_content_id", table_name="documents")
    op.drop_column("documents", "fallback_applied")
    op.drop_column("documents", "errors_json")
    op.drop_column("documents", "warnings_json")
    op.drop_column("documents", "sectioning_hint")
    op.drop_column("documents", "parser_used")
    op.drop_column("documents", "filename")
    op.drop_column("documents", "pitch_id")
    op.drop_column("documents", "content_id")
