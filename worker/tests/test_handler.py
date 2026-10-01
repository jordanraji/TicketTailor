import logging
from unittest.mock import AsyncMock

import pytest

from worker.adapters.web_push import SubscriptionExpiredError
from worker.handler import process_domain_event
from worker.schemas import (
    NotificationPayload,
    PushSubscriptionKeys,
    PushSubscriptionSchema,
    RecipientSchema,
)


def make_mock_sqs_record(body: str, message_id: str = "msg-123") -> dict:
    """Helper to generate a mock SQS record satisfying SqsModel."""
    return {
        "messageId": message_id,
        "receiptHandle": "mock-receipt-handle",
        "body": body,
        "attributes": {
            "ApproximateReceiveCount": "1",
            "SentTimestamp": "123456789",
            "SenderId": "mock-sender-id",
            "ApproximateFirstReceiveTimestamp": "123456789",
        },
        "messageAttributes": {},
        "md5OfBody": "mock-md5",
        "eventSource": "aws:sqs",
        "eventSourceARN": "arn:aws:sqs:ap-southeast-2:123456789012:queue",
        "awsRegion": "ap-southeast-2",
    }


@pytest.mark.asyncio
async def test_handle_event_updated_flow() -> None:
    mock_email = AsyncMock()
    mock_push = AsyncMock()

    payload = NotificationPayload(
        event_title="Awesome Concert",
        recipient=RecipientSchema(
            email="attendee@test.com",
            display_name="John Doe",
            push_subscription=PushSubscriptionSchema(
                endpoint="https://push.com/john",
                keys=PushSubscriptionKeys(p256dh="dh", auth="auth"),
            ),
        ),
    )

    await process_domain_event(
        event_type="event_updated",
        payload=payload,
        email_provider=mock_email,
        push_provider=mock_push,
    )

    mock_email.send_email.assert_called_once_with(
        "attendee@test.com",
        "Event Update: Awesome Concert",
        "<p>Hello John Doe,</p><p>An event you are attending, "
        "<strong>Awesome Concert</strong>, has been updated by "
        "the organiser.</p>",
    )
    mock_push.send_push.assert_called_once()
    push_args = mock_push.send_push.call_args[0]
    assert push_args[0]["endpoint"] == "https://push.com/john"
    assert "Awesome Concert" in push_args[1]


@pytest.mark.asyncio
async def test_handle_visibility_changed_flow() -> None:
    mock_email = AsyncMock()
    mock_push = AsyncMock()

    payload = NotificationPayload(
        event_title="Public Event Title",
        recipient=RecipientSchema(
            email="follower@test.com",
            display_name="Jane Follower",
            push_subscription=PushSubscriptionSchema(
                endpoint="https://push.com/jane",
                keys=PushSubscriptionKeys(p256dh="dh", auth="auth"),
            ),
        ),
    )

    await process_domain_event(
        event_type="visibility_changed",
        payload=payload,
        email_provider=mock_email,
        push_provider=mock_push,
    )

    mock_email.send_email.assert_called_once_with(
        "follower@test.com",
        "New Event Published: Public Event Title",
        "<p>Hello Jane Follower,</p><p>A club you follow has published "
        "a new event: <strong>Public Event Title</strong>.</p>",
    )
    mock_push.send_push.assert_called_once()
    push_args = mock_push.send_push.call_args[0]
    assert push_args[0]["endpoint"] == "https://push.com/jane"
    assert "Public Event Title" in push_args[1]


@pytest.mark.asyncio
async def test_expired_subscription_logging(caplog: pytest.LogCaptureFixture) -> None:
    mock_email = AsyncMock()
    mock_push = AsyncMock()
    mock_push.send_push.side_effect = SubscriptionExpiredError("Expired")

    payload = NotificationPayload(
        event_title="Title",
        recipient=RecipientSchema(
            email="expired@test.com",
            display_name="Expired Sub",
            push_subscription=PushSubscriptionSchema(
                endpoint="https://push.com/expired",
                keys=PushSubscriptionKeys(p256dh="dh", auth="auth"),
            ),
        ),
    )

    with caplog.at_level(logging.WARNING):
        await process_domain_event(
            event_type="event_updated",
            payload=payload,
            email_provider=mock_email,
            push_provider=mock_push,
        )

    # Email should still be sent
    mock_email.send_email.assert_called_once()
    # Warning about expired subscription should be logged
    assert (
        "Push subscription expired for endpoint https://push.com/expired" in caplog.text
    )


@pytest.mark.asyncio
async def test_unknown_event_type_skipped() -> None:
    mock_email = AsyncMock()
    mock_push = AsyncMock()

    payload = NotificationPayload(
        event_title="Title",
        recipient=RecipientSchema(email="test@test.com"),
    )

    await process_domain_event(
        event_type="unknown_type",
        payload=payload,
        email_provider=mock_email,
        push_provider=mock_push,
    )

    mock_email.send_email.assert_not_called()
    mock_push.send_push.assert_not_called()


@pytest.mark.asyncio
async def test_handle_rsvp_placed_flow() -> None:
    mock_email = AsyncMock()
    mock_push = AsyncMock()

    payload = NotificationPayload(
        event_title="Awesome Concert",
        recipient=RecipientSchema(
            email="attendee@test.com",
            display_name="John Doe",
        ),
    )

    await process_domain_event(
        event_type="rsvp_placed",
        payload=payload,
        email_provider=mock_email,
        push_provider=mock_push,
    )

    mock_email.send_email.assert_called_once_with(
        "attendee@test.com",
        "RSVP Confirmation: Awesome Concert",
        "<p>Hello John Doe,</p><p>Your RSVP for <strong>Awesome Concert</strong> "
        "has been placed successfully.</p>",
    )
    mock_push.send_push.assert_not_called()


@pytest.mark.asyncio
async def test_generic_dict_payload_skipped() -> None:
    mock_email = AsyncMock()
    mock_push = AsyncMock()

    payload = {
        "event_id": "some-id",
        "club_id": "some-club-id",
    }

    await process_domain_event(
        event_type="event_created",
        payload=payload,
        email_provider=mock_email,
        push_provider=mock_push,
    )

    mock_email.send_email.assert_not_called()
    mock_push.send_push.assert_not_called()
