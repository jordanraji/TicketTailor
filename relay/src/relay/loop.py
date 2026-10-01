"""The relay's long-running poll loop and process wiring."""

from __future__ import annotations

import asyncio
import logging
import signal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from relay.config import RelayConfig
from relay.publisher import LoggingPublisher, Publisher, SnsPublisher
from relay.service import OutboxRelay

logger = logging.getLogger("relay.loop")


def build_publisher(config: RelayConfig) -> Publisher:
    """Pick a publisher: SNS when a topic is configured, otherwise log-only."""
    if config.sns_topic_arn:
        logger.info("using SNS publisher (topic=%s)", config.sns_topic_arn)
        return SnsPublisher(config.sns_topic_arn, config.aws_region)
    logger.warning(
        "AWS_SNS_TOPIC_ARN not set - using logging publisher (no messages leave "
        "the process). Set it in production."
    )
    return LoggingPublisher()


async def run_loop(
    relay: OutboxRelay,
    poll_interval_seconds: float,
    *,
    stop_event: asyncio.Event,
) -> None:
    """Tick the relay until ``stop_event`` is set, sleeping between ticks but
    waking immediately on shutdown."""
    logger.info("relay started (poll interval %.2fs)", poll_interval_seconds)
    while not stop_event.is_set():
        await relay.tick()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_interval_seconds)
        except TimeoutError:
            pass
    logger.info("relay stopped")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = RelayConfig.from_env()
    engine = create_async_engine(config.database_url, future=True)
    sessionmaker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    relay = OutboxRelay(
        sessionmaker,
        build_publisher(config),
        publish_batch_size=config.publish_batch_size,
        transition_batch_size=config.transition_batch_size,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in ("SIGINT", "SIGTERM"):
        try:
            loop.add_signal_handler(getattr(signal, signal_name), stop_event.set)
        except (NotImplementedError, AttributeError):
            # Signal handlers are unavailable on some platforms (e.g. Windows);
            # the loop still exits cleanly on KeyboardInterrupt.
            pass

    try:
        await run_loop(relay, config.poll_interval_seconds, stop_event=stop_event)
    finally:
        await engine.dispose()
