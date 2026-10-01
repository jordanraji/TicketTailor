"""create refresh tokens table

Revision ID: 964e8204d37a
Revises: None
Create Date: 2026-05-31 01:16:46.319574

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "964e8204d37a"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_table("refresh_tokens", schema="auth")
