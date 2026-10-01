"""create clubs and memberships tables

Revision ID: 2c30f846bbee
Revises: None
Create Date: 2026-05-31 01:17:10.915538

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2c30f846bbee"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clubs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        schema="organisers",
    )
    op.create_table(
        "club_memberships",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "committee_member",
                "admin",
                name="membership_role",
                schema="organisers",
                inherit_schema=True,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["club_id"], ["organisers.clubs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "club_id", name="uq_club_memberships_user_club"),
        schema="organisers",
    )


def downgrade() -> None:
    op.drop_table("club_memberships", schema="organisers")
    op.drop_table("clubs", schema="organisers")
    op.execute("DROP TYPE IF EXISTS organisers.membership_role")
