---
status: "accepted"
date: 2026-06-03
decision-makers: [TicketTailor team]
consulted: [Daniel, Jordan]
informed: []
---

# Relay-side notification fan-out with hydrated messages

## Context and Problem Statement

ADR-0006 has the outbox relay publish thin domain events to SNS; ADR-0002/0010 frame the notification worker (AWS Lambda) as the consumer that delivers email and web push. The worker has been built **stateless and database-free** (PR #28) - it cannot query the database to resolve who should be notified or fetch their contact details. Something must therefore turn one domain event (e.g. a `visibility_changed` for a club with N followers) into N fully-addressed notifications. This ADR decides **where recipient resolution and contact-detail hydration happen, and the exact message contract** between relay and worker.

## Decision Drivers

* Reliability ASR (QA3) - at-least-once delivery must survive a partial fan-out; no lost or duplicated-and-undeduped notifications.
* Scalability ASR (QA1) - the FR5 flip must fan out to N=1,000 followers within p95 ≤ 30 s, off the API request path. (Target N=1,000; the executed run to date demonstrated N=300 - 300/300 delivered, p95 = 5.1 s - and argues the 1,000 target by extrapolation, ack latency staying flat as N grew 15x, 20 -> 300; see docs/test-reports/load-test-2026-06-06.md.)
* Operational simplicity - the worker is AWS Lambda; coupling Lambda to RDS (VPC wiring, connection-pool exhaustion under burst) is a known pain point we want to avoid.
* Module-boundary discipline - cross-module data access goes through service interfaces, not foreign table reads (the import-linter contract; the architecture-overview "module-talk rule").
* Privacy/security (QA4, ADR-0009) - notifications carry PII (email, web-push keys); that data now transits the message bus.

## Considered Options

* (a) **Worker resolves recipients** - relay publishes the thin domain event; the Lambda worker queries the DB for followers/attendees and contact details, then sends.
* (b) **Relay hydrates and fans out** - the relay resolves recipients, fetches contact details, and publishes one fully-populated message per recipient; the worker is a stateless sender.
* (c) **Dedicated fan-out service** - a new deployable between relay and worker doing resolution + hydration.

## Decision Outcome

Chosen option: **(b) relay hydrates and fans out**, because it keeps the worker stateless and database-free (no Lambda↔RDS coupling) while reusing the relay's existing DB access and outbox-publish loop, adding no new deployable.

Per relay tick, the **publish phase becomes a router**:

- **Notification events** are resolved to a recipient set, hydrated, and fanned out one message per recipient:

  | `event_type` | recipient set |
  | --- | --- |
  | `visibility_changed` | users following the organising club (`users.club_follows`) - FR5 |
  | `event_updated` | users who have RSVP'd to the event - FR7 |
  | `rsvp_placed` | the single attendee who RSVP'd (confirmation); the `user_id` is already in the outbox payload |

- **Non-notification events** (`event_created`, `rsvp_cancelled`, `club_membership_changed`) are **marked published without fan-out** - kept as durable audit rows, not delivered.

**Message contract** (mirrors `worker/src/worker/schemas.py` `DomainEvent` / `NotificationPayload`):

```json
{
  "id": "{outbox_row_id}:{recipient_user_id}:0",
  "event_type": "visibility_changed",
  "aggregate_id": "{event_id}",
  "payload": {
    "event_title": "Awesome Outdoor Concert",
    "recipient": {
      "email": "user@example.com",
      "display_name": "Jane Doe",
      "push_subscription": {
        "endpoint": "https://updates.push.services.com/v1/...",
        "keys": { "p256dh": "BBAA...", "auth": "1234..." }
      }
    }
  }
}
```

- **Dedup key** `id = {outbox_row_id}:{recipient_user_id}:{ordinal}` is deterministic across retries; the worker dedupes on it. MVP emits **one message per recipient** (ordinal `0`) carrying email + the recipient's **most recent** push subscription. The ordinal is reserved for future per-device fan-out.
- **`aggregate_id` is the event id** for every notification type (the subject of the notification); `event_title` is read from the `events` row the relay already has access to.
- **Recipient resolution + hydration go through service interfaces** (to be added):
  - `users.followers_for_club(club_id) -> list[user_id]` (reverse of the existing `get_followed_clubs`)
  - `users.contact_details_for(user_ids) -> list[Recipient]` (batch: email, display_name, latest push subscription)
  - `rsvp.attendees_for_event(event_id) -> list[user_id]`
- **Partial fan-out is all-or-nothing on the row**: a notification outbox row is stamped `published_at` only once **every** recipient message is accepted by the bus. On partial failure the row is left unpublished and the whole set is re-emitted next tick; the deterministic dedup key makes that safe. This refines ADR-0006's relay publish loop - per-message isolation still holds *across* outbox rows, but *within* a single fanned-out row it is all-or-nothing.

### Consequences

* Good - worker stays stateless/DB-free; scales as pure compute with no RDS connection management.
* Good - no new deployable; reuses the relay's loop and DB access.
* Good - one deterministic dedup key preserves at-least-once end-to-end under retry.
* Bad - the relay's data dependencies widen from "events + outbox" to also reading `users`, `club_follows`, `push_subscriptions`, and rsvp attendees (via service interfaces). The L2/L3 diagrams and the architecture-overview module table must be updated to match - drift here is a graded risk.
* Bad - PII (email, push keys) now transits SNS/SQS; requires SSE-KMS on the topic and queues (ADR-0009) and is a privacy-surface expansion.
* Bad - a 1,000-recipient flip is 1,000 hydrated publishes from one row; the fan-out query needs indexes (`club_follows.club_id`, `push_subscriptions.user_id`) and the relay's batch model needs to hold the QA1 SLO.

### Confirmation

* A **contract test** in the relay pins its message models against the worker's `DomainEvent`/`NotificationPayload` (compares `model_json_schema()`), failing CI on drift.
* Integration tests assert: each notification type resolves the correct recipient set; one message per recipient with a deterministic id; non-notification types are marked published without emitting; and a partial-fan-out failure leaves the row unpublished for safe re-emit.
* The L2/L3 d2 diagrams and `architecture-overview.md` are updated so the relay's responsibilities and data dependencies match the code.

## Pros and Cons of the Options

### (a) Worker resolves recipients

* Good - relay stays thin (events + outbox only); matches the current L2 view.
* Bad - Lambda needs RDS access: VPC wiring and connection-pool exhaustion under a 1,000-fan-out burst - the exact failure mode QA1 stresses.
* Bad - couples the stateless worker to the full domain schema.

### (b) Relay hydrates and fans out (chosen)

* Good - stateless worker; reuses existing relay DB access; no new deployable.
* Bad - widens the relay's responsibilities and puts PII on the bus (mitigations above).

### (c) Dedicated fan-out service

* Good - clean separation; relay and worker both stay focused.
* Bad - a fourth deployable to build, test, document, and defend - the cost ADR-0010 explicitly avoided. Not justified for a student-team MVP.

## More Information

Extends ADR-0006 (the relay now hydrates and fans out, not just thin-publishes) and the relay scope in ADR-0010; depends on ADR-0011 (web-push subscriptions) and ADR-0009 (SSE-KMS for PII on the bus). Contract source of truth: `worker/src/worker/schemas.py`. Revisit if multi-device push becomes in scope (use the reserved ordinal) or the fan-out query cannot hold the QA1 SLO (consider pre-materialising recipient lists or a dedicated consumer).
