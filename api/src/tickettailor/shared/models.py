import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OutboxEventType(enum.StrEnum):
    event_created = "event_created"
    event_updated = "event_updated"
    rsvp_placed = "rsvp_placed"
    rsvp_cancelled = "rsvp_cancelled"
    visibility_changed = "visibility_changed"
    club_membership_changed = "club_membership_changed"


class OutboxEvent(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        Index("idx_outbox_unpublished", "published_at", "created_at"),
        {"schema": "shared"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    aggregate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    event_type: Mapped[OutboxEventType] = mapped_column(
        Enum(
            OutboxEventType,
            name="outbox_event_type",
            schema="shared",
            inherit_schema=True,
        ),
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
