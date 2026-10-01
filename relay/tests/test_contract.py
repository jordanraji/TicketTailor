"""Contract test (ADR-0016): the relay's outbound message models must match the
worker's ``DomainEvent`` / ``NotificationPayload``, which the stateless worker
validates SQS messages against. This pins ``relay.contract`` to the worker's
schema and fails CI if they drift.

The worker's schema is imported by path (monorepo) rather than via a package
dependency - ``worker/src/worker/schemas.py`` only needs pydantic, which the
relay already has, so no heavy worker runtime deps are pulled in.
"""

import sys
from pathlib import Path

import pytest

from relay import contract

_WORKER_SRC = Path(__file__).resolve().parents[2] / "worker" / "src"
if str(_WORKER_SRC) not in sys.path:
    sys.path.insert(0, str(_WORKER_SRC))

from worker import schemas as worker_schemas  # noqa: E402  (path-dependent import)


@pytest.mark.parametrize(
    ("relay_model", "worker_model"),
    [
        (contract.DomainEvent, worker_schemas.DomainEvent),
        (contract.NotificationPayload, worker_schemas.NotificationPayload),
        (contract.RecipientSchema, worker_schemas.RecipientSchema),
        (contract.PushSubscriptionSchema, worker_schemas.PushSubscriptionSchema),
        (contract.PushSubscriptionKeys, worker_schemas.PushSubscriptionKeys),
    ],
)
def test_relay_models_match_worker_fields(relay_model, worker_model) -> None:  # type: ignore[no-untyped-def]
    assert set(relay_model.model_fields) == set(worker_model.model_fields)


def test_relay_message_validates_under_worker_schema() -> None:
    message = contract.DomainEvent(
        id="outbox-row:recipient-user:0",
        event_type="visibility_changed",
        aggregate_id="event-id",
        payload=contract.NotificationPayload(
            event_title="Awesome Outdoor Concert",
            recipient=contract.RecipientSchema(
                email="user@example.com",
                display_name="Jane Doe",
                push_subscription=contract.PushSubscriptionSchema(
                    endpoint="https://updates.push.services.com/v1/...",
                    keys=contract.PushSubscriptionKeys(
                        p256dh="BBAA...", auth="1234..."
                    ),
                ),
            ),
        ),
    )

    # The relay's serialised output must parse under the worker's model.
    parsed = worker_schemas.DomainEvent.model_validate_json(message.model_dump_json())

    assert parsed.id == message.id
    assert parsed.event_type == "visibility_changed"
    # The worker resolves the payload to its NotificationPayload (not the dict
    # branch of the union), preserving every field.
    assert isinstance(parsed.payload, worker_schemas.NotificationPayload)
    assert parsed.payload.event_title == "Awesome Outdoor Concert"
    assert parsed.payload.recipient.email == "user@example.com"
    assert parsed.payload.recipient.display_name == "Jane Doe"
    assert parsed.payload.recipient.push_subscription is not None
    assert parsed.payload.recipient.push_subscription.keys.p256dh == "BBAA..."
