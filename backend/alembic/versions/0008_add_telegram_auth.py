"""add telegram_id/username to users, nullable email/password, telegram_login_tokens

Revision ID: 0008_add_telegram_auth
Revises: 0007_add_subscriptions
Create Date: 2026-08-18

Adds "Войти через Telegram" (bot-initiated login/link, see
app/models/telegram_login_token.py). Purely additive except for widening
users.email/password_hash to nullable — a Telegram-only account has
neither. Existing rows are untouched (they already have both set), so
this is a metadata-only change with no data rewrite and no risk to the
two real production accounts.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_add_telegram_auth"
down_revision: Union[str, None] = "0007_add_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=True)
    op.alter_column(
        "users", "password_hash", existing_type=sa.String(length=255), nullable=True
    )
    op.add_column("users", sa.Column("telegram_id", sa.BigInteger(), nullable=True))
    op.add_column("users", sa.Column("telegram_username", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_users_telegram_id", "users", ["telegram_id"])
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    op.create_table(
        "telegram_login_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_username", sa.String(length=255), nullable=True),
        sa.Column("telegram_first_name", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_telegram_login_tokens_token_hash", "telegram_login_tokens", ["token_hash"])
    op.create_index("ix_telegram_login_tokens_user_id", "telegram_login_tokens", ["user_id"])
    op.create_index("ix_telegram_login_tokens_status", "telegram_login_tokens", ["status"])


def downgrade() -> None:
    op.drop_index("ix_telegram_login_tokens_status", table_name="telegram_login_tokens")
    op.drop_index("ix_telegram_login_tokens_user_id", table_name="telegram_login_tokens")
    op.drop_index("ix_telegram_login_tokens_token_hash", table_name="telegram_login_tokens")
    op.drop_table("telegram_login_tokens")

    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_constraint("uq_users_telegram_id", "users", type_="unique")
    op.drop_column("users", "telegram_username")
    op.drop_column("users", "telegram_id")
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=False)
