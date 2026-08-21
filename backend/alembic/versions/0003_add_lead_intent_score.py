"""add leads.intent_score / intent_signals (hidden-demand detection)

Revision ID: 0003_add_lead_intent_score
Revises: 0002_add_source_last_external_id
Create Date: 2026-08-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_lead_intent_score"
down_revision: Union[str, None] = "0002_add_source_last_external_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("intent_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "leads",
        sa.Column("intent_signals", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_leads_intent_score", "leads", ["intent_score"])


def downgrade() -> None:
    op.drop_index("ix_leads_intent_score", table_name="leads")
    op.drop_column("leads", "intent_signals")
    op.drop_column("leads", "intent_score")
