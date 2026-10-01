import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from tickettailor.shared.validation import StrictTextModel
from tickettailor.users.models import UserRole

schema_config = ConfigDict(from_attributes=True)


class UserCreate(StrictTextModel):
    email: EmailStr = Field(
        ...,
        description="Unique email address of the user",
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Plain text password, must be at least 8 characters",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name of the user",
    )


class UserUpdate(StrictTextModel):
    email: EmailStr | None = Field(
        None,
        description="Optional new email address",
    )
    password: str | None = Field(
        None,
        min_length=8,
        description="Optional new password (at least 8 characters)",
    )
    display_name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Optional new display name",
    )


class UserResponse(BaseModel):
    model_config = schema_config

    id: uuid.UUID
    email: EmailStr
    display_name: str
    role: UserRole
    created_at: datetime


class ClubFollowCreate(StrictTextModel):
    club_id: uuid.UUID = Field(
        ...,
        description="UUID of the club to follow",
    )


class ClubFollowResponse(BaseModel):
    model_config = schema_config

    id: uuid.UUID
    user_id: uuid.UUID
    club_id: uuid.UUID
    created_at: datetime


class PushSubscriptionCreate(StrictTextModel):
    endpoint: str = Field(
        ...,
        description="Browser push service endpoint URL",
    )
    p256dh: str = Field(
        ...,
        description="User public key for push notifications",
    )
    auth: str = Field(
        ...,
        description="Auth secret for push notifications",
    )


class PushSubscriptionResponse(BaseModel):
    model_config = schema_config

    id: uuid.UUID
    user_id: uuid.UUID
    endpoint: str
    created_at: datetime


class RecipientPushSubscription(BaseModel):
    model_config = schema_config

    endpoint: str
    p256dh: str
    auth: str


class RecipientContact(BaseModel):
    """A user's notification contact details, for the outbox relay's fan-out
    (ADR-0016). ``push_subscription`` is the user's most recent subscription,
    or None if they have none."""

    model_config = schema_config

    user_id: uuid.UUID
    email: EmailStr
    display_name: str
    push_subscription: RecipientPushSubscription | None = None
