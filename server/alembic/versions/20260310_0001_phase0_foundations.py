"""phase0 foundations

Revision ID: 20260310_0001
Revises:
Create Date: 2026-03-10 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260310_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("comparison_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("session_state", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"], unique=False)

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("chat_sessions.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("query_type", sa.String(length=64), nullable=True),
        sa.Column("classification", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"], unique=False)
    op.create_index("ix_chat_messages_role", "chat_messages", ["role"], unique=False)

    op.create_table(
        "evaluation_results",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("chat_sessions.id"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.String(length=36),
            sa.ForeignKey("chat_messages.id"),
            nullable=True,
        ),
        sa.Column("query_type", sa.String(length=64), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("scorecard", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("recommendation", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_evaluation_results_session_id", "evaluation_results", ["session_id"], unique=False
    )
    op.create_index(
        "ix_evaluation_results_query_type", "evaluation_results", ["query_type"], unique=False
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_path", sa.String(length=500), nullable=False),
        sa.Column("ingestion_status", sa.String(length=32), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_documents_source_path", "documents", ["source_path"], unique=True)
    op.create_index("ix_documents_document_type", "documents", ["document_type"], unique=False)

    op.create_table(
        "document_sections",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column("section_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("section_type", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("clause_id", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_document_sections_document_id", "document_sections", ["document_id"], unique=False
    )
    op.create_index(
        "ix_document_sections_section_key", "document_sections", ["section_key"], unique=False
    )
    op.create_index(
        "ix_document_sections_section_type", "document_sections", ["section_type"], unique=False
    )

    op.create_table(
        "document_facts",
        sa.Column("fact_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column(
            "section_id",
            sa.String(length=36),
            sa.ForeignKey("document_sections.id"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("predicate", sa.String(length=255), nullable=False),
        sa.Column("object_value", sa.Text(), nullable=False),
        sa.Column("qualifier", sa.String(length=255), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("extracted_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_document_facts_document_id",
        "document_facts",
        ["document_id"],
        unique=False,
    )
    op.create_index("ix_document_facts_section_id", "document_facts", ["section_id"], unique=False)

    op.create_table(
        "document_risks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(length=36),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column(
            "section_id",
            sa.String(length=36),
            sa.ForeignKey("document_sections.id"),
            nullable=False,
        ),
        sa.Column("risk_type", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("mitigation", sa.Text(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_document_risks_document_id",
        "document_risks",
        ["document_id"],
        unique=False,
    )
    op.create_index("ix_document_risks_section_id", "document_risks", ["section_id"], unique=False)
    op.create_index("ix_document_risks_risk_type", "document_risks", ["risk_type"], unique=False)
    op.create_index("ix_document_risks_severity", "document_risks", ["severity"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_document_risks_severity", table_name="document_risks")
    op.drop_index("ix_document_risks_risk_type", table_name="document_risks")
    op.drop_index("ix_document_risks_section_id", table_name="document_risks")
    op.drop_index("ix_document_risks_document_id", table_name="document_risks")
    op.drop_table("document_risks")

    op.drop_index("ix_document_facts_section_id", table_name="document_facts")
    op.drop_index("ix_document_facts_document_id", table_name="document_facts")
    op.drop_table("document_facts")

    op.drop_index("ix_document_sections_section_type", table_name="document_sections")
    op.drop_index("ix_document_sections_section_key", table_name="document_sections")
    op.drop_index("ix_document_sections_document_id", table_name="document_sections")
    op.drop_table("document_sections")

    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_index("ix_documents_source_path", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_evaluation_results_query_type", table_name="evaluation_results")
    op.drop_index("ix_evaluation_results_session_id", table_name="evaluation_results")
    op.drop_table("evaluation_results")

    op.drop_index("ix_chat_messages_role", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
