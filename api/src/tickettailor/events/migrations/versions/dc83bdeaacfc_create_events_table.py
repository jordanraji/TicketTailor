"""create events table

Revision ID: dc83bdeaacfc
Revises: None
Create Date: 2026-05-31 01:55:04.715142

"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "dc83bdeaacfc"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("club_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeogFromText",
                name="geography",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_free", sa.Boolean(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column(
            "visibility",
            sa.Enum(
                "club_only",
                "public",
                name="event_visibility",
                schema="events",
                inherit_schema=True,
            ),
            nullable=False,
        ),
        sa.Column("transition_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("image_s3_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="events",
    )
    op.create_index(
        "idx_events_location",
        "events",
        ["location"],
        unique=False,
        schema="events",
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_events_location",
        table_name="events",
        schema="events",
        postgresql_using="gist",
    )
    op.drop_table("events", schema="events")
    op.execute("DROP TYPE IF EXISTS events.event_visibility")
