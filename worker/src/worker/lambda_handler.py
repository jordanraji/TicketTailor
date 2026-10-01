import asyncio
import json
import logging
import os
import sys
from typing import Any, cast

from aws_lambda_powertools.utilities.parser import parse
from aws_lambda_powertools.utilities.parser.envelopes import SnsSqsEnvelope, SqsEnvelope

from worker.adapters.email import get_email_provider
from worker.adapters.web_push import WebPushProvider
from worker.config import settings
from worker.handler import process_domain_event
from worker.schemas import DomainEvent

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# The AWS Lambda runtime pre-configures the root logger, which makes the
# basicConfig above a no-op there (it only takes effect for local/test runs).
# The runtime defaults the level to WARNING, which would suppress our INFO logs
# - including the "Notification ack" line the load test measures fan-out latency
# from. Set the level explicitly so INFO reaches CloudWatch in Lambda too.
logging.getLogger().setLevel(_LOG_LEVEL)
logger = logging.getLogger("worker.lambda_handler")
logger.setLevel(_LOG_LEVEL)

# Initialize providers outside the handler.
# This takes advantage of AWS Lambda container reuse (warm starts)
# to preserve HTTP client connections.
email_provider = get_email_provider(
    email_provider_type=settings.EMAIL_PROVIDER,
    from_address=settings.EMAIL_FROM_ADDRESS,
    resend_api_key=settings.RESEND_API_KEY,
    smtp_host=settings.SMTP_HOST,
    smtp_port=settings.SMTP_PORT,
    timeout=settings.DELIVERY_TIMEOUT_SECONDS,
)
push_provider = WebPushProvider(
    private_key=settings.VAPID_PRIVATE_KEY,
    claims_email=settings.VAPID_CLAIMS_EMAIL,
    timeout=settings.DELIVERY_TIMEOUT_SECONDS,
)


def get_envelope(event: dict[str, Any]) -> Any:
    """Dynamically determine the envelope type based SQS records structure."""
    try:
        records = event.get("Records", [])
        if records:
            first_body = json.loads(records[0].get("body", "{}"))
            if (
                isinstance(first_body, dict)
                and "Message" in first_body
                and "TopicArn" in first_body
            ):
                logger.info("SNS wrapper envelope (SnsSqsEnvelope) detected.")
                return SnsSqsEnvelope
    except Exception:
        pass
    logger.info("Raw SQS message envelope (SqsEnvelope) detected.")
    return SqsEnvelope


async def process_parsed_events(parsed_events: list[DomainEvent]) -> None:
    """Process a batch of DomainEvent objects asynchronously."""
    for event in parsed_events:
        logger.info(f"Processing event: {event.event_type}")
        await process_domain_event(
            event_type=event.event_type,
            payload=event.payload,
            email_provider=email_provider,
            push_provider=push_provider,
        )
        # Per-recipient delivery ack, one line per message. event_id is the
        # aggregate (the events.id); it lets the QA1-load fan-out latency be
        # computed from CloudWatch logs against the flip time (see
        # tests/load/README.md).
        logger.info(
            f"Notification ack: event_id={event.aggregate_id} "
            f"msg_id={event.id} type={event.event_type}"
        )


def run_coroutine(coro: Any) -> Any:
    """Run an async coroutine synchronously.

    If an event loop is already running in the current thread (e.g. in pytest),
    it runs the coroutine in a separate thread to avoid event loop conflicts.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import threading

        result = []
        exception = []

        def target() -> None:
            try:
                result.append(asyncio.run(coro))
            except Exception as e:
                exception.append(e)

        thread = threading.Thread(target=target)
        thread.start()
        thread.join()

        if exception:
            raise exception[0]
        return result[0] if result else None
    else:
        return asyncio.run(coro)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for the SQS Event Source Mapping trigger.

    The event source mapping is configured with
    ``function_response_types = ["ReportBatchItemFailures"]`` (see
    infra/modules/compute/worker.tf), so this handler MUST return a
    ``{"batchItemFailures": [{"itemIdentifier": <messageId>}, ...]}`` response.
    Records are processed one at a time so a single failed delivery only
    redelivers that message (and eventually dead-letters after maxReceiveCount)
    instead of the whole batch - and so a failure is never silently dropped.
    """
    records = event.get("Records", [])
    if not records:
        logger.info("No records received in Lambda event trigger.")
        return {"batchItemFailures": []}

    logger.info(f"Lambda triggered with batch of {len(records)} SQS records.")

    failures: list[dict[str, str]] = []
    for record in records:
        message_id = record.get("messageId")
        try:
            # Parse and process one record at a time so the messageId stays
            # associated with its event (the batch envelope parse discards it).
            single_record_event = {"Records": [record]}
            envelope = get_envelope(single_record_event)
            parsed_events = cast(
                list[DomainEvent],
                parse(
                    event=single_record_event,
                    model=DomainEvent,
                    envelope=envelope,
                ),
            )
            run_coroutine(process_parsed_events(parsed_events))
        except Exception:
            logger.exception(
                f"Record {message_id} failed; reporting for SQS redelivery."
            )
            if message_id is not None:
                failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}
