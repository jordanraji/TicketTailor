"""add partial index for the visibility-transition scan

Revision ID: c4a9e1f2b3d5
Revises: b7e2f1a4c9d0
Create Date: 2026-06-06 10:30:00.000000

The outbox relay polls for due visibility flips every tick with
``WHERE visibility = 'club_only' AND transition_at IS NOT NULL
AND transition_at <= now() ORDER BY transition_at`` (relay/service.py, FR5).
Without an index that is a sequential scan of the whole events table on every
poll, which the QA1-load spike makes expensive. This partial index on
``transition_at`` over only the club-only rows keeps the scan proportional to
the pending-transition set, not the table. Matches the optimisation noted in
docs/architecture-overview.md and infra/README.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4a9e1f2b3d5"
down_revision: str | None = "b7e2f1a4c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_events_transition_scan",
        "events",
        ["transition_at"],
        unique=False,
        schema="events",
        postgresql_where=sa.text("visibility = 'club_only'"),
    )


def downgrade() -> None:
    op.drop_index(
        "idx_events_transition_scan",
        table_name="events",
        schema="events",
    )
