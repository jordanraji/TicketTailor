import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Rsvp(Base):
    __tablename__ = "rsvps"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_rsvps_user_event"),
        # The (user_id, event_id) unique index serves user_id-prefix lookups,
        # but not queries filtered by event_id alone (count/attendees per
        # event, the RSVP read path, reconciliation, fan-out). Without this
        # index those sequential-scan the whole table as RSVP volume grows.
        Index("ix_rsvps_event_id", "event_id"),
        {"schema": "rsvp"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,  # Logical reference to users.users.id (cross-module boundary)
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,  # Logical reference to events.events.id (cross-module boundary)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
