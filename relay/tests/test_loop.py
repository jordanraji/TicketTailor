"""Unit tests for the relay's process wiring (no database required).

Covers publisher selection (SNS when a topic is configured, logging otherwise)
and the poll loop's start/stop lifecycle.
"""

import asyncio

import pytest

from relay.config import RelayConfig
from relay.contract import DomainEvent
from relay.loop import build_publisher, run_loop
from relay.publisher import LoggingPublisher


def _config(sns_topic_arn: str | None) -> RelayConfig:
    return RelayConfig(
        database_url="postgresql+asyncpg://unused/unused",
        poll_interval_seconds=0.01,
        publish_batch_size=100,
        transition_batch_size=100,
        sns_topic_arn=sns_topic_arn,
        aws_region="ap-southeast-2",
    )


class _StubSnsPublisher:
    def __init__(self, topic_arn: str, region: str) -> None:
        self.topic_arn = topic_arn
        self.region = region

    async def publish(self, message: DomainEvent) -> None:  # pragma: no cover
        pass


class _CountingRelay:
    """Stand-in for OutboxRelay: counts ticks and stops after ``stop_after``."""

    def __init__(self, stop_event: asyncio.Event, stop_after: int = 1) -> None:
        self.ticks = 0
        self._stop_event = stop_event
        self._stop_after = stop_after

    async def tick(self) -> None:
        self.ticks += 1
        if self.ticks >= self._stop_after:
            self._stop_event.set()


def test_build_publisher_without_topic_uses_logging() -> None:
    publisher = build_publisher(_config(sns_topic_arn=None))
    assert isinstance(publisher, LoggingPublisher)


def test_build_publisher_with_topic_uses_sns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Substitute the real SNS publisher (which needs boto3 + AWS) with a stub so
    # we exercise the selection branch without those dependencies.
    monkeypatch.setattr("relay.loop.SnsPublisher", _StubSnsPublisher)

    publisher = build_publisher(_config(sns_topic_arn="arn:aws:sns:::topic"))

    assert isinstance(publisher, _StubSnsPublisher)
    assert publisher.topic_arn == "arn:aws:sns:::topic"


async def test_run_loop_ticks_until_stopped() -> None:
    stop_event = asyncio.Event()
    relay = _CountingRelay(stop_event, stop_after=3)

    await run_loop(relay, poll_interval_seconds=0.01, stop_event=stop_event)

    assert relay.ticks == 3


async def test_run_loop_exits_immediately_when_already_stopped() -> None:
    stop_event = asyncio.Event()
    stop_event.set()
    relay = _CountingRelay(stop_event, stop_after=1)

    await run_loop(relay, poll_interval_seconds=0.01, stop_event=stop_event)

    assert relay.ticks == 0
