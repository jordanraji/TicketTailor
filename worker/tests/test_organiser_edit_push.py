"""FR7 integration: when an organiser edits an event, every RSVP'd attendee
receives a web push (and email) notification.

Drives full SQS ``event_updated`` messages through ``lambda_handler`` with spy
providers. The relay fans these out per RSVP'd attendee
(``relay/tests/test_fanout.py``); here we assert the worker delivers the push to
each attendee, including push-only recipients.
"""

import json
from unittest.mock import AsyncMock, patch

from worker.lambda_handler import lambda_handler


def _sqs_record(body: dict, message_id: str = "msg-1") -> dict:
    return {
        "messageId": message_id,
        "receiptHandle": "mock-receipt-handle",
        "body": json.dumps(body),
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


def _event_updated_message(
    event_id: str, user_id: str, email: str | None, with_push: bool = True
) -> dict:
    recipient: dict = {"email": email, "display_name": "Attendee"}
    if with_push:
        recipient["push_subscription"] = {
            "endpoint": f"https://push.example/{user_id}",
            "keys": {"p256dh": "dh", "auth": "auth"},
        }
    return {
        "id": f"{event_id}:{user_id}:0",
        "aggregate_id": event_id,
        "event_type": "event_updated",
        "payload": {"event_title": "Rescheduled Concert", "recipient": recipient},
    }


@patch("worker.lambda_handler.push_provider", new_callable=AsyncMock)
@patch("worker.lambda_handler.email_provider", new_callable=AsyncMock)
def test_organiser_edit_pushes_to_attendee(
    mock_email: AsyncMock, mock_push: AsyncMock
) -> None:
    event = {
        "Records": [
            _sqs_record(_event_updated_message("evt-1", "user-1", "attendee@test.com"))
        ]
    }

    response = lambda_handler(event, None)

    assert response["batchItemFailures"] == []
    mock_push.send_push.assert_called_once()
    sub, payload = mock_push.send_push.call_args[0]
    assert sub["endpoint"] == "https://push.example/user-1"
    assert "Rescheduled Concert" in payload
    _to, subject, _html = mock_email.send_email.call_args[0]
    assert subject == "Event Update: Rescheduled Concert"


@patch("worker.lambda_handler.push_provider", new_callable=AsyncMock)
@patch("worker.lambda_handler.email_provider", new_callable=AsyncMock)
def test_edit_pushes_to_every_rsvpd_attendee(
    mock_email: AsyncMock, mock_push: AsyncMock
) -> None:
    attendees = [("user-1", "a@test.com"), ("user-2", "b@test.com")]
    event = {
        "Records": [
            _sqs_record(_event_updated_message("evt-7", uid, email), uid)
            for uid, email in attendees
        ]
    }

    response = lambda_handler(event, None)

    assert response["batchItemFailures"] == []
    assert mock_push.send_push.call_count == 2


@patch("worker.lambda_handler.push_provider", new_callable=AsyncMock)
@patch("worker.lambda_handler.email_provider", new_callable=AsyncMock)
def test_push_only_attendee_still_receives_push(
    mock_email: AsyncMock, mock_push: AsyncMock
) -> None:
    # FR7 is fundamentally a web-push requirement: an attendee with no email but
    # a push subscription must still be pushed to.
    event = {
        "Records": [
            _sqs_record(
                _event_updated_message("evt-3", "user-1", email=None, with_push=True)
            )
        ]
    }

    response = lambda_handler(event, None)

    assert response["batchItemFailures"] == []
    mock_push.send_push.assert_called_once()
    mock_email.send_email.assert_not_called()
