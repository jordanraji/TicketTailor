"""add category column to events

Revision ID: b7e2f1a4c9d0
Revises: dc83bdeaacfc
Create Date: 2026-06-03 12:00:00.000000

Free-form interest category for the map's combined geo-radius + category filter
(FR2; the browse-events query is `... AND category = ?`). Nullable and additive
so existing events stay valid; a controlled vocabulary can be layered on later.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2f1a4c9d0"
down_revision: str | None = "dc83bdeaacfc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("category", sa.String(), nullable=True),
        schema="events",
    )


def downgrade() -> None:
    op.drop_column("events", "category", schema="events")
