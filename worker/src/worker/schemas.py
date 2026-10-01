from typing import Any

from pydantic import BaseModel


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionSchema(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys


class RecipientSchema(BaseModel):
    email: str | None = None
    display_name: str | None = None
    push_subscription: PushSubscriptionSchema | None = None


class NotificationPayload(BaseModel):
    event_title: str
    recipient: RecipientSchema


class DomainEvent(BaseModel):
    """Pydantic model for domain events received via SQS."""

    id: str
    event_type: str
    aggregate_id: str
    payload: NotificationPayload | dict[str, Any]
