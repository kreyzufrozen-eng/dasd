"""add leads.reasoning

Revision ID: 0006_add_lead_reasoning
Revises: 0005_add_search_profile_links
Create Date: 2026-08-18

Этап 8: persists LeadAnalysis.reasoning_short (already returned by the AI
on every analysis, previously discarded) so the "Отфильтровано AI" page
can show WHY a message was or wasn't judged a lead, not just its score.
Purely additive — one nullable column, no backfill needed (existing rows
just have reasoning=NULL, same graceful-empty handling as any other
optional Lead field).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_add_lead_reasoning"
down_revision: Union[str, None] = "0005_add_search_profile_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("reasoning", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "reasoning")
