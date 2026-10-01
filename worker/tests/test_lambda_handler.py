import json
from unittest.mock import AsyncMock, patch

import pytest

from worker.adapters.web_push import SubscriptionExpiredError
from worker.handler import process_domain_event
from worker.lambda_handler import lambda_handler
from worker.schemas import (
    DomainEvent,
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


@patch("worker.lambda_handler.process_parsed_events", new_callable=AsyncMock)
def test_lambda_handler_processes_batch(mock_process: AsyncMock) -> None:
    body1 = {
        "id": "msg-1",
        "aggregate_id": "agg-1",
        "event_type": "event_updated",
        "payload": {
            "event_title": "Concert",
            "recipient": {
                "email": "test@test.com",
                "display_name": "Test User",
            },
        },
    }
    body2 = {
        "id": "msg-2",
        "aggregate_id": "agg-2",
        "event_type": "visibility_changed",
        "payload": {
            "event_title": "Public Event",
            "recipient": {
                "email": "test2@test.com",
                "display_name": "Test User 2",
            },
        },
    }

    event = {
        "Records": [
            make_mock_sqs_record(json.dumps(body1), "msg-1"),
            make_mock_sqs_record(json.dumps(body2), "msg-2"),
        ]
    }

    response = lambda_handler(event, None)

    # New contract: per-record processing with a ReportBatchItemFailures
    # response. All records succeed here (process is mocked), so no failures.
    assert response["batchItemFailures"] == []
    # One call per record, each with a single-element parsed list.
    assert mock_process.call_count == 2
    first = mock_process.call_args_list[0][0][0]
    second = mock_process.call_args_list[1][0][0]
    assert len(first) == 1
    assert first[0].id == "msg-1"
    assert first[0].event_type == "event_updated"
    assert len(second) == 1
    assert second[0].id == "msg-2"
    assert second[0].event_type == "visibility_changed"


@patch("worker.lambda_handler.process_parsed_events", new_callable=AsyncMock)
def test_lambda_handler_partial_batch_failure(mock_process: AsyncMock) -> None:
    """QA3 at-least-once: a transient failure on ONE record of a batch reports
    only that record in batchItemFailures (for SQS redelivery) while the good
    record is acked (absent from the failures list)."""
    good_body = {
        "id": "msg-good",
        "aggregate_id": "agg-good",
        "event_type": "event_updated",
        "payload": {
            "event_title": "Concert",
            "recipient": {
                "email": "good@test.com",
                "display_name": "Good User",
            },
        },
    }
    bad_body = {
        "id": "msg-bad",
        "aggregate_id": "agg-bad",
        "event_type": "event_updated",
        "payload": {
            "event_title": "Concert",
            "recipient": {
                "email": "bad@test.com",
                "display_name": "Bad User",
            },
        },
    }

    # Records are processed one at a time, so each call receives a single-element
    # parsed list. Raise a transient error for the bad record only; the good one
    # completes normally.
    async def side_effect(parsed_events: list[DomainEvent]) -> None:
        if parsed_events[0].id == "msg-bad":
            raise RuntimeError("transient delivery failure")

    mock_process.side_effect = side_effect

    event = {
        "Records": [
            make_mock_sqs_record(json.dumps(good_body), "msg-good"),
            make_mock_sqs_record(json.dumps(bad_body), "msg-bad"),
        ]
    }

    response = lambda_handler(event, None)

    # Only the failing record is reported (by its SQS messageId); the good
    # record is acked and must NOT appear in the failures list.
    assert response["batchItemFailures"] == [{"itemIdentifier": "msg-bad"}]
    assert {"itemIdentifier": "msg-good"} not in response["batchItemFailures"]
    # Both records were attempted (the failure of one does not skip the other).
    assert mock_process.call_count == 2


@patch("worker.lambda_handler.process_parsed_events", new_callable=AsyncMock)
def test_lambda_handler_handles_generic_payload(mock_process: AsyncMock) -> None:
    body = {
        "id": "msg-3",
        "aggregate_id": "agg-3",
        "event_type": "rsvp_cancelled",
        "payload": {
            "rsvp_id": "some-rsvp-id",
            "user_id": "some-user-id",
        },
    }

    event = {
        "Records": [
            make_mock_sqs_record(json.dumps(body), "msg-3"),
        ]
    }

    response = lambda_handler(event, None)
    assert response["batchItemFailures"] == []
    mock_process.assert_called_once()
    parsed_list = mock_process.call_args[0][0]
    assert len(parsed_list) == 1
    assert parsed_list[0].event_type == "rsvp_cancelled"
    assert isinstance(parsed_list[0].payload, dict)


@patch("worker.lambda_handler.process_parsed_events", new_callable=AsyncMock)
def test_lambda_handler_empty_event(mock_process: AsyncMock) -> None:
    event = {"Records": []}
    response = lambda_handler(event, None)
    assert response["batchItemFailures"] == []
    mock_process.assert_not_called()


def _push_recipient_payload() -> NotificationPayload:
    """A recipient with a push subscription (and no email) so the only delivery
    channel exercised is web push."""
    return NotificationPayload(
        event_title="Concert",
        recipient=RecipientSchema(
            email=None,
            display_name="Push User",
            push_subscription=PushSubscriptionSchema(
                endpoint="https://push.example/user",
                keys=PushSubscriptionKeys(p256dh="dh", auth="auth"),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_process_domain_event_reraises_on_transient_channel_failure() -> None:
    """QA3 at-least-once: a transient delivery-channel failure RE-RAISES out of
    process_domain_event so the Lambda can report the SQS record in
    batchItemFailures and SQS redelivers it (rather than silently dropping it)."""
    mock_email = AsyncMock()
    mock_push = AsyncMock()
    mock_push.send_push.side_effect = RuntimeError("provider 503")

    with pytest.raises(RuntimeError, match="provider 503"):
        await process_domain_event(
            event_type="event_updated",
            payload=_push_recipient_payload(),
            email_provider=mock_email,
            push_provider=mock_push,
        )

    mock_push.send_push.assert_called_once()


@pytest.mark.asyncio
async def test_process_domain_event_swallows_expired_subscription() -> None:
    """A permanent failure (expired push subscription) is SWALLOWED: no failure
    is surfaced, so SQS does not redeliver an undeliverable push."""
    mock_email = AsyncMock()
    mock_push = AsyncMock()
    mock_push.send_push.side_effect = SubscriptionExpiredError("expired")

    # Must NOT raise - an expired subscription is not redeliverable.
    await process_domain_event(
        event_type="event_updated",
        payload=_push_recipient_payload(),
        email_provider=mock_email,
        push_provider=mock_push,
    )

    mock_push.send_push.assert_called_once()
