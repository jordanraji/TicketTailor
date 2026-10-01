import enum
import struct
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from geoalchemy2 import Geography
from sqlalchemy import Boolean, DateTime, Enum, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EventVisibility(enum.StrEnum):
    club_only = "club_only"
    public = "public"


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_location", "location", postgresql_using="gist"),
        {"schema": "events"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    club_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,  # Logical reference to organisers.clubs.id
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,  # Logical reference to users.users.id (cross-module boundary)
    )
    title: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    category: Mapped[str | None] = mapped_column(
        String,
        nullable=True,  # Free-form interest category for the map filter (FR2)
    )
    location: Mapped[Geography] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    is_free: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=True,
    )
    visibility: Mapped[EventVisibility] = mapped_column(
        Enum(
            EventVisibility,
            name="event_visibility",
            schema="events",
            inherit_schema=True,
        ),
        nullable=False,
        default=EventVisibility.club_only,
    )
    transition_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    image_s3_key: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def _point_coordinates(self) -> tuple[Decimal, Decimal]:
        location = cast(Any, self.location)
        data = getattr(location, "data", location)

        if isinstance(data, str):
            wkt = data.strip()
            point_start = wkt.upper().find("POINT")
            if point_start == -1:
                raise ValueError("Unsupported event location format.")

            start = wkt.find("(", point_start)
            end = wkt.find(")", point_start)
            longitude, latitude = wkt[start + 1 : end].split()
            return Decimal(latitude), Decimal(longitude)

        if isinstance(data, bytes | bytearray | memoryview):
            blob = bytes(data)
            if len(blob) < 21:
                raise ValueError("Unsupported event location format.")

            endian = "<" if blob[0] == 1 else ">"
            geometry_type = struct.unpack(f"{endian}I", blob[1:5])[0]
            offset = 5

            # PostGIS EWKB includes SRID when this flag is present.
            if geometry_type & 0x20000000:
                offset += 4

            longitude, latitude = struct.unpack(
                f"{endian}dd",
                blob[offset : offset + 16],
            )
            return Decimal(str(latitude)), Decimal(str(longitude))

        raise ValueError("Unsupported event location format.")

    @property
    def latitude(self) -> Decimal:
        latitude, _ = self._point_coordinates()
        return latitude

    @property
    def longitude(self) -> Decimal:
        _, longitude = self._point_coordinates()
        return longitude
