"""create outbox table

Revision ID: c1796a71a737
Revises: None
Create Date: 2026-05-31 01:31:48.447271

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1796a71a737"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("aggregate_id", sa.UUID(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "event_created",
                "event_updated",
                "rsvp_placed",
                "rsvp_cancelled",
                "visibility_changed",
                "club_membership_changed",
                name="outbox_event_type",
                schema="shared",
                inherit_schema=True,
            ),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="shared",
    )
    op.create_index(
        "idx_outbox_unpublished",
        "outbox",
        ["published_at", "created_at"],
        unique=False,
        schema="shared",
    )


def downgrade() -> None:
    op.drop_index("idx_outbox_unpublished", table_name="outbox", schema="shared")
    op.drop_table("outbox", schema="shared")
    op.execute("DROP TYPE IF EXISTS shared.outbox_event_type")
