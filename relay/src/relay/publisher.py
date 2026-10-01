"""Message-bus publishers for the relay.

The relay depends only on the :class:`Publisher` protocol. Production uses
:class:`SnsPublisher`; local runs use :class:`LoggingPublisher`; tests use
:class:`CollectingPublisher`. This keeps the relay runnable and fully testable
without AWS (or LocalStack) - the SNS wiring lands when the infra does.

Messages are the hydrated, per-recipient :class:`~relay.contract.DomainEvent`
the worker consumes (ADR-0016); ``id`` is the deterministic dedup key.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol, runtime_checkable

from relay.contract import DomainEvent

logger = logging.getLogger("relay.publisher")


@runtime_checkable
class Publisher(Protocol):
    async def publish(self, message: DomainEvent) -> None: ...


class LoggingPublisher:
    """Default local/dev publisher: logs each message instead of hitting SNS."""

    async def publish(self, message: DomainEvent) -> None:
        logger.info("publish %s (id=%s)", message.event_type, message.id)


class CollectingPublisher:
    """In-memory publisher for tests; records every message it receives."""

    def __init__(self) -> None:
        self.messages: list[DomainEvent] = []

    async def publish(self, message: DomainEvent) -> None:
        self.messages.append(message)


class SnsPublisher:
    """Publishes to an SNS topic (ADR-0006).

    boto3 is synchronous, so each call is dispatched to a worker thread to avoid
    blocking the relay's event loop. boto3 is imported lazily so it is only
    required when this publisher is actually used (install the ``sns`` extra).
    """

    def __init__(
        self,
        topic_arn: str,
        region: str,
        connect_timeout: float = 5.0,
        read_timeout: float = 10.0,
        max_attempts: int = 3,
    ) -> None:
        import boto3  # noqa: PLC0415 - lazy import; optional `sns` extra
        from botocore.config import Config  # noqa: PLC0415 - lazy with boto3

        self._topic_arn = topic_arn
        # Bound the SNS call: botocore defaults to 60s connect/read which, while
        # the relay holds the outbox row lock across the publish, would pin a DB
        # connection and stall the poll loop on any SNS hiccup. A failed publish
        # leaves the row unmarked, so it is retried on the next tick.
        self._client = boto3.client(
            "sns",
            region_name=region,
            config=Config(
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                retries={"max_attempts": max_attempts, "mode": "standard"},
            ),
        )

    async def publish(self, message: DomainEvent) -> None:
        await asyncio.to_thread(
            self._client.publish,
            TopicArn=self._topic_arn,
            Message=message.model_dump_json(),
            MessageAttributes={
                # Lets per-channel SQS subscriptions filter by event type, and
                # gives the worker a stable dedup key without parsing the body.
                "event_type": {
                    "DataType": "String",
                    "StringValue": message.event_type,
                },
                "dedup_id": {"DataType": "String", "StringValue": message.id},
            },
        )
