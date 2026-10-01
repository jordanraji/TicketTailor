"""add index on rsvps.event_id

Revision ID: a1f2c3d4e5b6
Revises: 5d0ce1662d61
Create Date: 2026-06-06 00:00:00.000000

The (user_id, event_id) unique index does not serve event_id-only lookups
(count/attendees per event, the RSVP read path, reconciliation, fan-out).
This index prevents those from sequential-scanning the table under the RSVP
spike load.

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1f2c3d4e5b6"
down_revision: str | None = "5d0ce1662d61"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_rsvps_event_id",
        "rsvps",
        ["event_id"],
        schema="rsvp",
    )


def downgrade() -> None:
    op.drop_index("ix_rsvps_event_id", table_name="rsvps", schema="rsvp")
