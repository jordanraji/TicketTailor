import asyncio
import json
import logging
import string
from typing import Any

from worker.adapters.email import EmailProvider
from worker.adapters.web_push import SubscriptionExpiredError, WebPushProvider
from worker.schemas import NotificationPayload

logger = logging.getLogger(__name__)


async def send_single_push(
    sub: dict[str, Any],
    payload: str,
    push_provider: WebPushProvider,
) -> None:
    """Send a single web push and log if the subscription is expired."""
    try:
        await push_provider.send_push(sub, payload)
    except SubscriptionExpiredError:
        # ARCHITECTURAL NOTE:
        # Since the Notification Worker is database-free (stateless) to prevent
        # RDS connection limits and VPC cold-start bottlenecks, we cannot write
        # directly to the DB to delete expired subscriptions (returning 410/404).
        #
        # A future refinement must clean up these stale subscriptions by either:
        # 1. Calling an internal secure API route (e.g. DELETE /push/subscriptions)
        #    via HTTP using `httpx`.
        # 2. Emitting a `push_subscription_expired` event back to SQS, which is
        #    consumed by the modular monolith/relay to handle the database delete.
        #
        # This is a PERMANENT failure: retrying cannot succeed, so we log and
        # swallow it (the message must not be redelivered for this).
        logger.warning(
            f"Push subscription expired for endpoint {sub.get('endpoint')}. "
            "Please notify API/Relay to remove this subscription."
        )
    except Exception:
        # Transient failure (network, provider 5xx, timeout). Re-raise so the
        # caller can report the SQS message in batchItemFailures and SQS
        # redelivers it (at-least-once delivery, ADR-0006).
        logger.exception(f"Error sending web push to endpoint {sub.get('endpoint')}")
        raise


async def process_domain_event(
    event_type: str,
    payload: NotificationPayload | dict[str, Any],
    email_provider: EmailProvider,
    push_provider: WebPushProvider,
) -> None:
    """Route and process domain events to deliver email and push notifications."""
    if not isinstance(payload, NotificationPayload):
        logger.info(
            f"Event type '{event_type}' has no fanned-out notification payload. "
            "Skipped."
        )
        return

    event_title = payload.event_title
    recipient = payload.recipient

    if event_type == "event_updated":
        subject = f"Event Update: {event_title}"
        email_template = (
            "<p>Hello $display_name,</p>"
            "<p>An event you are attending, <strong>$event_title</strong>, "
            "has been updated by the organiser.</p>"
        )
        push_title = "Event Updated"
        push_body = f"The event '{event_title}' has been updated."

    elif event_type == "visibility_changed":
        subject = f"New Event Published: {event_title}"
        email_template = (
            "<p>Hello $display_name,</p>"
            "<p>A club you follow has published a new event: "
            "<strong>$event_title</strong>.</p>"
        )
        push_title = "New Event Published"
        push_body = f"A club you follow has published the event '{event_title}'."

    elif event_type == "rsvp_placed":
        subject = f"RSVP Confirmation: {event_title}"
        email_template = (
            "<p>Hello $display_name,</p>"
            "<p>Your RSVP for <strong>$event_title</strong> has been placed "
            "successfully.</p>"
        )
        push_title = "RSVP Confirmed"
        push_body = f"Your RSVP for '{event_title}' has been confirmed."

    else:
        logger.info(f"Event type '{event_type}' requires no notifications. Skipped.")
        return

    email_task = None
    if recipient.email:
        name = recipient.display_name or "User"
        template = string.Template(email_template)
        html_content = template.safe_substitute(
            display_name=name, event_title=event_title
        )
        email_task = email_provider.send_email(recipient.email, subject, html_content)

    push_task = None
    if recipient.push_subscription:
        sub_dict = {
            "endpoint": recipient.push_subscription.endpoint,
            "keys": {
                "p256dh": recipient.push_subscription.keys.p256dh,
                "auth": recipient.push_subscription.keys.auth,
            },
        }
        push_payload = json.dumps({"title": push_title, "body": push_body})
        push_task = send_single_push(sub_dict, push_payload, push_provider)

    tasks = []
    if email_task:
        tasks.append(email_task)
    if push_task:
        tasks.append(push_task)

    if not tasks:
        logger.info("No delivery details found for this recipient.")
        return

    results = await asyncio.gather(*tasks, return_exceptions=True)
    errors = [r for r in results if isinstance(r, Exception)]
    for err in errors:
        logger.error(f"Notification delivery failed with exception: {err}")
    if errors:
        # At-least-once: re-raise so the Lambda reports this record in
        # batchItemFailures and SQS redelivers it, rather than silently
        # dropping a failed notification (which would never reach the DLQ).
        # Permanent failures (expired push subscription) are swallowed in
        # send_single_push and never reach here. A redelivery may resend an
        # already-delivered channel (e.g. email succeeded, push failed); that
        # duplicate is the accepted trade-off for not losing notifications
        # (see ADR-0006 dedup discussion).
        raise errors[0]
