"""add index on club_follows.club_id for relay fan-out

Revision ID: f3a9c1b27d04
Revises: 2767f591826b
Create Date: 2026-06-03 00:00:00.000000

The outbox relay resolves a club's followers with
`SELECT user_id FROM users.club_follows WHERE club_id = ?` (ADR-0016 fan-out).
The uq_club_follows_user_club index is on (user_id, club_id), whose leading
column is user_id, so it cannot serve a club_id-only lookup - add a dedicated
index. push_subscriptions.user_id needs no index: uq_push_subscriptions_user_
endpoint is on (user_id, endpoint) and already covers user_id-prefixed reads.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f3a9c1b27d04"
down_revision: str | None = "2767f591826b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_club_follows_club_id",
        "club_follows",
        ["club_id"],
        schema="users",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_club_follows_club_id",
        table_name="club_follows",
        schema="users",
    )
