"""The relay→worker message contract (ADR-0016).

Mirrors ``worker/src/worker/schemas.py`` (`DomainEvent` / `NotificationPayload`)
so the relay emits exactly what the stateless worker consumes. ``test_contract``
pins these against the worker's models and fails CI on drift.
"""

from __future__ import annotations

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
    id: str
    event_type: str
    aggregate_id: str
    payload: NotificationPayload | dict[str, Any]
