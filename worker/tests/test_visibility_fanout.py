"""FR5 integration: the worker delivers a notification to each follower when a
club-only event flips to public.

Drives full SQS events through ``lambda_handler`` (real Powertools parsing +
routing) with spy providers, so it exercises the parse -> route -> deliver path
end to end. The relay-side fan-out itself (one message per follower) is covered
by ``relay/tests/test_fanout.py``; here we assert the worker delivers each
fanned-out message correctly.
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


def _visibility_message(event_id: str, user_id: str, email: str) -> dict:
    return {
        "id": f"{event_id}:{user_id}:0",
        "aggregate_id": event_id,
        "event_type": "visibility_changed",
        "payload": {
            "event_title": "Public Launch Party",
            "recipient": {
                "email": email,
                "display_name": "Follower",
                "push_subscription": {
                    "endpoint": f"https://push.example/{user_id}",
                    "keys": {"p256dh": "dh", "auth": "auth"},
                },
            },
        },
    }


@patch("worker.lambda_handler.push_provider", new_callable=AsyncMock)
@patch("worker.lambda_handler.email_provider", new_callable=AsyncMock)
def test_visibility_change_delivers_to_follower(
    mock_email: AsyncMock, mock_push: AsyncMock
) -> None:
    event = {
        "Records": [
            _sqs_record(_visibility_message("evt-1", "user-1", "follower@test.com"))
        ]
    }

    response = lambda_handler(event, None)

    assert response["batchItemFailures"] == []
    mock_email.send_email.assert_called_once()
    to_addr, subject, _html = mock_email.send_email.call_args[0]
    assert to_addr == "follower@test.com"
    assert subject == "New Event Published: Public Launch Party"
    mock_push.send_push.assert_called_once()


@patch("worker.lambda_handler.push_provider", new_callable=AsyncMock)
@patch("worker.lambda_handler.email_provider", new_callable=AsyncMock)
def test_visibility_fanout_batch_reaches_every_follower(
    mock_email: AsyncMock, mock_push: AsyncMock
) -> None:
    # A fan-out arrives at the worker as one message per follower.
    followers = [
        ("user-1", "a@test.com"),
        ("user-2", "b@test.com"),
        ("user-3", "c@test.com"),
    ]
    event = {
        "Records": [
            _sqs_record(_visibility_message("evt-9", uid, email), uid)
            for uid, email in followers
        ]
    }

    response = lambda_handler(event, None)

    assert response["batchItemFailures"] == []
    assert mock_email.send_email.call_count == 3
    assert mock_push.send_push.call_count == 3
    delivered = {call.args[0] for call in mock_email.send_email.call_args_list}
    assert delivered == {"a@test.com", "b@test.com", "c@test.com"}
