"""add legal_documents, user_legal_acceptances, audit_logs, raw_items.retention_until

Revision ID: 0009_add_legal_audit
Revises: 0008_add_telegram_auth
Create Date: 2026-08-18

Legal/privacy compliance scaffolding — three new tables plus one nullable
column. Purely additive; no data rewrite of existing rows.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_add_legal_audit"
down_revision: Union[str, None] = "0008_add_telegram_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "legal_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("type", "version", name="uq_legal_doc_type_version"),
    )
    op.create_index("ix_legal_documents_type", "legal_documents", ["type"])

    op.create_table(
        "user_legal_acceptances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("legal_documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("document_version", sa.String(length=32), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_legal_acceptances_user_id", "user_legal_acceptances", ["user_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.add_column("raw_items", sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("raw_items", "retention_until")

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_user_legal_acceptances_user_id", table_name="user_legal_acceptances")
    op.drop_table("user_legal_acceptances")

    op.drop_index("ix_legal_documents_type", table_name="legal_documents")
    op.drop_table("legal_documents")
