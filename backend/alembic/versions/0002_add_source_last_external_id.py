"""add sources.last_external_id (per-source watermark for restart recovery)

Revision ID: 0002_add_source_last_external_id
Revises: 0001_initial_schema
Create Date: 2026-08-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_source_last_external_id"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("last_external_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "last_external_id")
