"""create calendar tokens table

Revision ID: 4597a3af58f0
Revises: None
Create Date: 2026-05-31 01:30:47.299965

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4597a3af58f0"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calendar_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
        schema="calendar",
    )


def downgrade() -> None:
    op.drop_table("calendar_tokens", schema="calendar")
