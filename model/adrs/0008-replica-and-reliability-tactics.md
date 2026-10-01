---
status: "accepted"
date: 2026-05-09
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Read replica and reliability tactics

## Context and Problem Statement

The reliability ASR (QA3) requires that event and attendee data stay consistent across replicas during high-frequency updates and that RSVP counts and event-status changes don't drift. Reliability is more than replication: idempotency, transactional outbox (ADR-0006), and reconciliation jobs are also needed.

## Decision Drivers

* Reliability ASR - RSVP counts and event status correct under load and across failure.
* Scalability ASR - read traffic for the map and event-detail endpoints shouldn't compete with writes.
* Operational simplicity - managed replication is preferred to bespoke clustering.

## Considered Options

* (a) Single-instance Postgres, no replica.
* (b) Postgres with one read replica, replication tactics only.
* (c) Postgres with one read replica plus idempotent writes plus transactional outbox plus periodic reconciliation.

## Decision Outcome

Chosen option: **(c) Postgres + read replica + idempotent writes + outbox + reconciliation**, because the reliability ASR is not satisfied by replication alone. The reliability story has four legs:

1. **Replication.** RDS-managed primary + at least one read replica. Map and event-detail reads route to the replica; writes go to primary.
2. **Idempotent RSVP writes.** Unique constraint on `(user_id, event_id)`; toggle keyed by the same pair. Repeating a toggle never double-counts.
3. **Transactional outbox** (ADR-0006). Domain events durable from the moment the business write commits; consumers dedupe by notification ID.
4. **Reconciliation.** Periodic job comparing the live counter (ADR-0005) to `SELECT COUNT(*) FROM rsvps WHERE event_id = ?` and correcting drift.

### Consequences

* Good - read replica relieves the primary of map traffic.
* Good - idempotent writes mean retries are safe (clients can retry RSVP toggle without fear).
* Good - outbox + reconciliation give a defensible answer to "what happens if X fails mid-burst?" for every X.
* Bad - replica lag. Reads from the replica may briefly miss a recent write. Read-after-write requirements (e.g., the user's own RSVP just submitted) must be explicitly routed to the primary.
* Bad - RDS replication is managed, but failover behaviour during the load test must be observed and documented.

### Confirmation

* RDS configuration includes at least one read replica.
* `rsvps` table has a unique constraint on `(user_id, event_id)`.
* Outbox + relay implemented per ADR-0006.
* Reconciliation job runs nightly and on demand (`RsvpService.reconcile_all`, implemented 2026-06-03).
* Counter drift under a concurrent burst and reconciliation of induced drift are validated locally in `api/src/tickettailor/rsvp/tests/test_rsvp_reliability.py` (QA3-replica, QA3-idempotent, QA3-reconcile).
* `tests/reliability/test_primary_failover.py` (RDS failover mid-burst) remains pending the load-test infrastructure - it needs a deployed primary + replica to exercise.

## Pros and Cons of the Options

### (a) Single-instance, no replica

* Good - simplest.
* Bad - fails the reliability ASR's "across replicas" requirement.

### (b) Replica only

* Good - one moving part (replication).
* Bad - incomplete. Replication doesn't address counter drift, message loss, or reconciliation.

### (c) Replica + idempotency + outbox + reconciliation

* Good - defensible reliability story end-to-end.
* Bad - more moving parts.

## More Information

Reliability tests document each tactic. The reliability section of the report's Evaluation reads from [`../../docs/traceability.md`](../../docs/traceability.md) rows QA3-*.
