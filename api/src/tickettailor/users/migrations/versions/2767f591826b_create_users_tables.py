"""create users tables

Revision ID: 2767f591826b
Revises: None
Create Date: 2026-05-31 01:17:41.003362

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2767f591826b"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "student",
                "committee_member",
                "admin",
                name="user_role",
                schema="users",
                inherit_schema=True,
            ),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        schema="users",
    )
    op.create_table(
        "club_follows",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "club_id", name="uq_club_follows_user_club"),
        schema="users",
    )
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("p256dh", sa.String(), nullable=False),
        sa.Column("auth", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "endpoint", name="uq_push_subscriptions_user_endpoint"
        ),
        schema="users",
    )


def downgrade() -> None:
    op.drop_table("push_subscriptions", schema="users")
    op.drop_table("club_follows", schema="users")
    op.drop_table("users", schema="users")
    op.execute("DROP TYPE IF EXISTS users.user_role")
