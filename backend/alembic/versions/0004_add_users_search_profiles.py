"""add users, search_profiles; make leads N:1 with raw_items

Revision ID: 0004_add_users_search_profiles
Revises: 0003_add_lead_intent_score
Create Date: 2026-08-18

Stage 1 of the SaaS migration (see PROJECT_AUDIT.md). The key structural
change: `leads.raw_item_id` was unique (one RawItem -> at most one Lead,
system-wide). Different users can now find the same message to be a lead
or not, so Lead becomes scoped per-SearchProfile: unique on
(raw_item_id, search_profile_id) instead.

To do that without breaking the ~450 Leads already on production, this
migration also creates one "legacy" User (the site owner, who's been the
sole real user so far) and one default SearchProfile matching the
persona that was previously hardcoded into app/ai/prompts.py, then
backfills every existing Lead onto that profile. Nothing about how those
existing leads are found or scored changes — only that they're now
attributed to a real profile instead of being implicitly global.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_users_search_profiles"
down_revision: Union[str, None] = "0003_add_lead_intent_score"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Generated once at authoring time (bcrypt hash of a random password, not
# committed anywhere else) — NOT the plaintext, which was surfaced to the
# site owner out-of-band. This exists purely so the one production account
# that already has real data isn't left passwordless; it's meant to be
# changed via POST /api/auth/change-password immediately after first login.
_LEGACY_PASSWORD_HASH = "$2b$12$mlebmar3HwGti4ki77p4/ecBt2Df/NZUZQU8/O0R9bADYa1Bo7jGS"
_LEGACY_EMAIL = "kreyzufrozen@gmail.com"
_LEGACY_SERVICES = [
    "веб-дизайн",
    "разработка сайтов",
    "лендинги",
    "корпоративные сайты",
    "интернет-магазины",
    "редизайн",
]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "search_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("profession", sa.String(length=255), nullable=True),
        sa.Column("profession_description", sa.Text(), nullable=True),
        sa.Column("services", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("technologies", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("target_clients", sa.String(length=255), nullable=True),
        sa.Column("preferred_niches", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("excluded_niches", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("min_budget", sa.Float(), nullable=True),
        sa.Column("max_budget", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="RUB"),
        sa.Column("geography", sa.String(length=255), nullable=True),
        sa.Column("languages", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("lead_types", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("notification_threshold", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ai_profile_context", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_search_profiles_user_id", "search_profiles", ["user_id"])

    # --- data migration: legacy owner account + default profile ---
    connection = op.get_bind()

    users_table = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("email", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("is_admin", sa.Boolean),
        sa.column("is_active", sa.Boolean),
    )
    legacy_user_id = connection.execute(
        users_table.insert()
        .values(
            email=_LEGACY_EMAIL,
            password_hash=_LEGACY_PASSWORD_HASH,
            is_admin=True,
            is_active=True,
        )
        .returning(users_table.c.id)
    ).scalar_one()

    search_profiles_table = sa.table(
        "search_profiles",
        sa.column("id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("profession", sa.String),
        sa.column("services", sa.JSON),
        sa.column("notification_threshold", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )
    legacy_profile_id = connection.execute(
        search_profiles_table.insert()
        .values(
            user_id=legacy_user_id,
            name="Веб-разработка",
            profession="Веб-дизайнер / веб-разработчик",
            services=_LEGACY_SERVICES,
            notification_threshold=60,
            is_active=True,
        )
        .returning(search_profiles_table.c.id)
    ).scalar_one()

    # --- leads: attach search_profile_id, then swap the uniqueness rule ---
    op.add_column("leads", sa.Column("search_profile_id", sa.Integer(), nullable=True))
    connection.execute(
        sa.text("UPDATE leads SET search_profile_id = :profile_id"),
        {"profile_id": legacy_profile_id},
    )
    op.alter_column("leads", "search_profile_id", nullable=False)
    op.create_foreign_key(
        "fk_leads_search_profile_id",
        "leads",
        "search_profiles",
        ["search_profile_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_leads_search_profile_id", "leads", ["search_profile_id"])

    op.drop_constraint("leads_raw_item_id_key", "leads", type_="unique")
    op.create_index("ix_leads_raw_item_id", "leads", ["raw_item_id"])
    op.create_unique_constraint(
        "uq_leads_raw_item_search_profile", "leads", ["raw_item_id", "search_profile_id"]
    )


def downgrade() -> None:
    # Only safe to run if every raw_item still has at most one Lead (true
    # right after this migration, not necessarily true later once more
    # than one SearchProfile exists) — this recreates a single-column
    # UNIQUE constraint that duplicate (raw_item_id, *) rows would violate.
    op.drop_constraint("uq_leads_raw_item_search_profile", "leads", type_="unique")
    op.drop_index("ix_leads_raw_item_id", table_name="leads")
    op.create_unique_constraint("leads_raw_item_id_key", "leads", ["raw_item_id"])
    op.drop_index("ix_leads_search_profile_id", table_name="leads")
    op.drop_constraint("fk_leads_search_profile_id", "leads", type_="foreignkey")
    op.drop_column("leads", "search_profile_id")

    op.drop_index("ix_search_profiles_user_id", table_name="search_profiles")
    op.drop_table("search_profiles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
