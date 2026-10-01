import uuid
from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tickettailor.events.models import EventVisibility
from tickettailor.shared.validation import StrictTextModel

schema_config = ConfigDict(from_attributes=True)
request_config = ConfigDict(extra="forbid")


class EventCreate(StrictTextModel):
    model_config = request_config

    club_id: uuid.UUID = Field(
        ...,
        description="Club that owns the event",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Public title of the event",
    )
    category: str | None = Field(
        None,
        max_length=100,
        description="Optional interest category used by the map filter (FR2)",
    )
    latitude: Decimal = Field(
        ...,
        ge=Decimal("-90"),
        le=Decimal("90"),
        description="Latitude of the event location",
    )
    longitude: Decimal = Field(
        ...,
        ge=Decimal("-180"),
        le=Decimal("180"),
        description="Longitude of the event location",
    )
    starts_at: datetime = Field(
        ...,
        description="Timezone-aware event start time",
    )
    is_free: bool = Field(
        True,
        description="Whether the event is free to attend",
    )
    price: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        description="Ticket price when the event is not free",
    )
    visibility: EventVisibility = Field(
        EventVisibility.club_only,
        description="Initial visibility of the event",
    )
    transition_at: datetime | None = Field(
        None,
        description="Optional time when a club-only event becomes public",
    )
    image_s3_key: str | None = Field(
        None,
        max_length=1024,
        description="Optional S3 object key for the event image",
    )

    @model_validator(mode="after")
    def validate_pricing(self) -> Self:
        if self.is_free and self.price is not None:
            raise ValueError("Free events must not include a price.")
        if not self.is_free and self.price is None:
            raise ValueError("Ticketed events must include a price.")
        return self


class EventUpdate(StrictTextModel):
    model_config = request_config

    title: str | None = Field(
        None,
        min_length=1,
        max_length=200,
        description="Updated event title",
    )
    category: str | None = Field(
        None,
        max_length=100,
        description="Updated interest category, or null to clear it",
    )
    latitude: Decimal | None = Field(
        None,
        ge=Decimal("-90"),
        le=Decimal("90"),
        description="Updated latitude of the event location",
    )
    longitude: Decimal | None = Field(
        None,
        ge=Decimal("-180"),
        le=Decimal("180"),
        description="Updated longitude of the event location",
    )
    starts_at: datetime | None = Field(
        None,
        description="Updated event start time",
    )
    is_free: bool | None = Field(
        None,
        description="Whether the event is free to attend",
    )
    price: Decimal | None = Field(
        None,
        ge=Decimal("0"),
        description="Updated ticket price, or null for free events",
    )
    visibility: EventVisibility | None = Field(
        None,
        description="Updated event visibility",
    )
    transition_at: datetime | None = Field(
        None,
        description="Updated club-only to public transition time",
    )
    image_s3_key: str | None = Field(
        None,
        max_length=1024,
        description="Updated S3 object key for the event image",
    )

    @model_validator(mode="after")
    def validate_update_fields(self) -> Self:
        has_latitude = self.latitude is not None
        has_longitude = self.longitude is not None
        if has_latitude != has_longitude:
            raise ValueError("Latitude and longitude must be updated together.")

        pricing_fields = {"is_free", "price"}
        updated_pricing_fields = pricing_fields.intersection(self.model_fields_set)
        if updated_pricing_fields and updated_pricing_fields != pricing_fields:
            raise ValueError("is_free and price must be updated together.")

        if updated_pricing_fields:
            if self.is_free and self.price is not None:
                raise ValueError("Free events must not include a price.")
            if not self.is_free and self.price is None:
                raise ValueError("Ticketed events must include a price.")

        return self


class EventResponse(BaseModel):
    model_config = schema_config

    id: uuid.UUID
    club_id: uuid.UUID
    created_by: uuid.UUID
    title: str
    category: str | None
    latitude: Decimal
    longitude: Decimal
    starts_at: datetime
    is_free: bool
    price: Decimal | None
    visibility: EventVisibility
    transition_at: datetime | None
    image_s3_key: str | None
    created_at: datetime
    updated_at: datetime
    distance_m: float | None = Field(
        None,
        description="Metres from the query point; set only for geo-radius searches",
    )

    @model_validator(mode="after")
    def round_public_coordinates(self) -> Self:
        if self.visibility == EventVisibility.public:
            self.latitude = self.latitude.quantize(Decimal("0.001"))
            self.longitude = self.longitude.quantize(Decimal("0.001"))
        return self


class EventListResponse(BaseModel):
    items: list[EventResponse]
    next_cursor: str | None = None
