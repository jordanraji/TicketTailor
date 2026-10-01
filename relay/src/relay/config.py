"""Relay runtime configuration.

Database, AWS region, and SNS topic are read from the shared API settings so the
relay and API agree on the same primary store and topic. Relay-specific knobs
(poll cadence, batch sizes) come from the environment with sensible defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from tickettailor.shared.config import settings


@dataclass(frozen=True)
class RelayConfig:
    database_url: str
    poll_interval_seconds: float
    publish_batch_size: int
    transition_batch_size: int
    sns_topic_arn: str | None
    aws_region: str

    @classmethod
    def from_env(cls) -> RelayConfig:
        return cls(
            database_url=settings.DATABASE_URL,
            poll_interval_seconds=float(
                os.getenv("RELAY_POLL_INTERVAL_SECONDS", "1.0")
            ),
            publish_batch_size=int(os.getenv("RELAY_PUBLISH_BATCH_SIZE", "100")),
            transition_batch_size=int(os.getenv("RELAY_TRANSITION_BATCH_SIZE", "100")),
            sns_topic_arn=settings.AWS_SNS_TOPIC_ARN,
            aws_region=settings.AWS_REGION,
        )
