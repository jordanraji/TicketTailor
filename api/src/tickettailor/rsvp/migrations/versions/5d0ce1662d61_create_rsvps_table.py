"""create rsvps table

Revision ID: 5d0ce1662d61
Revises: None
Create Date: 2026-05-31 01:30:23.576914

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5d0ce1662d61"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rsvps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "event_id", name="uq_rsvps_user_event"),
        schema="rsvp",
    )


def downgrade() -> None:
    op.drop_table("rsvps", schema="rsvp")
