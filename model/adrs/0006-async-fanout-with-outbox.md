---
status: "accepted"
date: 2026-05-09
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Async fan-out with transactional outbox

## Context and Problem Statement

When an event flips club-only → public (FR5) or an organiser edits an event with N RSVPs (FR7), the system must notify N users without blocking the API response. A naive fan-out from inside the API request blocks the request thread on the upstream push provider's latency and fails under burst. A fire-and-forget publish to a message bus loses notifications if the bus is briefly unavailable.

## Decision Drivers

* Scalability ASR - fan-out happens off the API request path so the API stays responsive during a flip.
* Reliability ASR - no notification is lost even if the message bus is briefly unavailable.
* Operational simplicity.
* Idempotency at the consumer - duplicates are tolerable, drops are not.

## Considered Options

* (a) Direct synchronous fan-out from inside the API request.
* (b) Direct asynchronous publish to the message bus from inside the API request, no outbox.
* (c) Transactional outbox: the API writes a domain event to an `outbox` table inside the same transaction as the business write; a relay process reads the outbox and publishes to the message bus; per-channel queues subscribe.

## Decision Outcome

Chosen option: **(c) transactional outbox**, because it gives at-least-once delivery - the publish is committed atomically with the business change, the relay is the only thing that can fail, and the relay can retry. This satisfies both the scalability ASR (fan-out is async, off the request path) and the reliability ASR (no lost notifications).

### Consequences

* Good - domain events are durable from the moment the business write commits. No race between commit and publish.
* Good - at-least-once delivery: consumers must be idempotent (notification IDs deduplicated by the worker).
* Good - clear audit trail in the outbox table.
* Bad - the relay is a new operational concern. Either a sidecar process or a thread inside the worker.
* Bad - at-least-once means consumers must dedupe. Push providers are typically idempotent on a notification ID, so this is mostly free.

### Confirmation

* `events`, `rsvp`, and any other module that publishes domain events writes to the outbox table inside the same DB transaction.
* The relay is implemented with `FOR UPDATE SKIP LOCKED` semantics so multiple relay instances can run safely.
* `relay/tests/test_redelivery.py` interrupts the relay mid-fan-out (a publish failure leaves the same DB state a crash-before-commit would) and asserts the unpublished row is redelivered on the next tick. The cross-process SQS → Lambda redelivery (true worker kill) is an AWS-runtime property exercised by the load-test infrastructure.
* Notifications carry a stable ID (`{outbox_row_id}:{recipient_id}:0`); redelivery re-sends the identical ID, so at-least-once delivery is deduplicable. Consumer-side dedup currently relies on push-provider/SQS idempotency - a worker-side dedup store is a noted follow-up, not yet implemented.

## Pros and Cons of the Options

### (a) Synchronous fan-out

* Good - trivial to implement.
* Bad - API latency spikes during a flip; can time out.
* Bad - fails scalability ASR's headline scenario.

### (b) Async publish, no outbox

* Good - simple.
* Bad - silent message loss if the bus is briefly unavailable. Fails reliability ASR.

### (c) Outbox + relay

* Good - atomic durability with at-least-once delivery.
* Good - same pattern works for both push notifications and email.
* Bad - relay is a new moving part; tests must cover relay failure and redelivery.

## More Information

The outbox table lives in the primary store (ADR-0008). The relay is its own deployable; it both publishes outbox rows (this ADR) and runs scheduled domain mutations (ADR-0010, currently the FR5 visibility transition). Both responsibilities share the relay's poll loop.
