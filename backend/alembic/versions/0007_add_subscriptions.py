"""add subscription_plans, subscriptions, usage_counters

Revision ID: 0007_add_subscriptions
Revises: 0006_add_lead_reasoning
Create Date: 2026-08-18

Этап 11 of the multi-search-profile SaaS ТЗ (see IMPLEMENTATION_PLAN.md
§10) — pure architecture prep, no payment provider exists to integrate
with. Purely additive: three new tables, plus a data seed (one "Free"
plan row) and a backfill (every existing user gets a Subscription to it)
so the read-only "your plan/usage" panel has real numbers for existing
accounts, not just new ones.
"""
import datetime as dt
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_add_subscriptions"
down_revision: Union[str, None] = "0006_add_lead_reasoning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FREE_PLAN_LIMITS = dict(
    max_search_profiles=3,
    max_sources_per_profile=10,
    max_ai_analyses_per_month=1000,
)


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False, unique=True),
        sa.Column("max_search_profiles", sa.Integer(), nullable=False),
        sa.Column("max_sources_per_profile", sa.Integer(), nullable=False),
        sa.Column("max_ai_analyses_per_month", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="RUB"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    op.create_table(
        "usage_counters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ai_analyses_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "period_start", name="uq_usage_user_period"),
    )
    op.create_index("ix_usage_counters_user_id", "usage_counters", ["user_id"])

    connection = op.get_bind()
    plans_table = sa.table(
        "subscription_plans",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("max_search_profiles", sa.Integer),
        sa.column("max_sources_per_profile", sa.Integer),
        sa.column("max_ai_analyses_per_month", sa.Integer),
        sa.column("price", sa.Float),
        sa.column("currency", sa.String),
    )
    result = connection.execute(
        plans_table.insert()
        .values(name="Free", price=None, currency="RUB", **_FREE_PLAN_LIMITS)
        .returning(plans_table.c.id)
    )
    free_plan_id = result.scalar_one()

    now = dt.datetime.now(dt.timezone.utc)
    connection.execute(
        sa.text(
            """
            INSERT INTO subscriptions (user_id, plan_id, status, current_period_start, created_at)
            SELECT id, :plan_id, 'active', :now, :now
            FROM users
            """
        ),
        {"plan_id": free_plan_id, "now": now},
    )


def downgrade() -> None:
    op.drop_index("ix_usage_counters_user_id", table_name="usage_counters")
    op.drop_table("usage_counters")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("subscription_plans")
