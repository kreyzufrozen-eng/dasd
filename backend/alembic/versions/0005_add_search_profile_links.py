"""add search_profile_sources, search_profile_keywords; extend sources/keywords/lead_feedback

Revision ID: 0005_add_search_profile_links
Revises: 0004_add_users_search_profiles
Create Date: 2026-08-18

Этап 2 of the multi-search-profile SaaS ТЗ (see IMPLEMENTATION_PLAN.md).
Purely additive — new tables plus nullable columns on existing ones, no
data migration, no risk to the ~513 production Leads or existing
sources/keywords rows. This is what lets each SearchProfile own its own
source list and keyword list without duplicating the shared Source/
Keyword catalog rows (a Source stays one row shared by every profile that
watches it; the link + its enabled flag lives here instead).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_add_search_profile_links"
down_revision: Union[str, None] = "0004_add_users_search_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "search_profile_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "search_profile_id",
            sa.Integer(),
            sa.ForeignKey("search_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("search_profile_id", "source_id", name="uq_sps_profile_source"),
    )
    op.create_index(
        "ix_search_profile_sources_search_profile_id",
        "search_profile_sources",
        ["search_profile_id"],
    )
    op.create_index(
        "ix_search_profile_sources_source_id", "search_profile_sources", ["source_id"]
    )

    op.create_table(
        "search_profile_keywords",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "search_profile_id",
            sa.Integer(),
            sa.ForeignKey("search_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "keyword_id",
            sa.Integer(),
            sa.ForeignKey("keywords.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("text", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("search_profile_id", "keyword_id", name="uq_spk_profile_keyword"),
    )
    op.create_index(
        "ix_search_profile_keywords_search_profile_id",
        "search_profile_keywords",
        ["search_profile_id"],
    )
    op.create_index("ix_search_profile_keywords_keyword_id", "search_profile_keywords", ["keyword_id"])
    op.create_index("ix_search_profile_keywords_category", "search_profile_keywords", ["category"])
    op.create_index("ix_search_profile_keywords_enabled", "search_profile_keywords", ["enabled"])

    op.add_column("sources", sa.Column("category", sa.String(length=64), nullable=True))
    op.add_column(
        "sources",
        sa.Column(
            "added_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.add_column(
        "keywords",
        sa.Column("is_global", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.add_column("lead_feedback", sa.Column("action", sa.String(length=32), nullable=True))
    op.add_column(
        "lead_feedback",
        sa.Column(
            "search_profile_id",
            sa.Integer(),
            sa.ForeignKey("search_profiles.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # Backfill: every existing feedback row's search_profile_id, from the
    # Lead it points at — cheap and correct since Lead already has exactly
    # one search_profile_id (Stage 1). New rows going forward get this set
    # at write time by the API/bot handler, not by a trigger.
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE lead_feedback
            SET search_profile_id = leads.search_profile_id
            FROM leads
            WHERE lead_feedback.lead_id = leads.id
            """
        )
    )


def downgrade() -> None:
    op.drop_column("lead_feedback", "search_profile_id")
    op.drop_column("lead_feedback", "action")
    op.drop_column("keywords", "is_global")
    op.drop_column("sources", "added_by_user_id")
    op.drop_column("sources", "category")
    op.drop_index("ix_search_profile_keywords_enabled", table_name="search_profile_keywords")
    op.drop_index("ix_search_profile_keywords_category", table_name="search_profile_keywords")
    op.drop_index("ix_search_profile_keywords_keyword_id", table_name="search_profile_keywords")
    op.drop_index(
        "ix_search_profile_keywords_search_profile_id", table_name="search_profile_keywords"
    )
    op.drop_table("search_profile_keywords")
    op.drop_index("ix_search_profile_sources_source_id", table_name="search_profile_sources")
    op.drop_index(
        "ix_search_profile_sources_search_profile_id", table_name="search_profile_sources"
    )
    op.drop_table("search_profile_sources")
