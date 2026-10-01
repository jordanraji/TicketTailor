---
status: "accepted"
date: 2026-05-09
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Atomic counter store for RSVP aggregate count

## Context and Problem Statement

FR3 requires a persisted, dynamically updated aggregate attendee count that stays correct under concurrent toggles. The reliability ASR (QA3) requires the count to stay correct during high-frequency updates and across replica failure. A naive implementation - increment a column under a row lock - bottlenecks on the row, sacrificing scalability.

## Decision Drivers

* Scalability ASR - bursty toggles during a hot event must not bottleneck on a single row lock.
* Reliability ASR - count must reconcile to the truth across replicas.
* Idempotency - toggling the same `(user_id, event_id)` repeatedly must not double-count.
* Operational simplicity - the team has limited capacity for bespoke consistency machinery.

## Considered Options

* (a) Postgres row-level lock per event, increment a counter column.
* (b) Redis `INCR`/`DECR` as the live counter, with periodic flush to Postgres.
* (c) Compute the count on read by `SELECT COUNT(*) FROM rsvps WHERE event_id = ?`.

## Decision Outcome

Chosen option: **(b) Redis `INCR`/`DECR` for the live count, with Postgres as the durable store**, because it gives high-throughput atomic increments without contending on a relational row, while Postgres remains the system of record for the underlying RSVP rows. A periodic reconciliation job compares the Redis counter to the row count and corrects drift.

Idempotency is enforced at two layers. Redis `SET NX EX` acts as a cheap application-level gate: if the key already exists the request returns `200 OK` without touching Postgres. The Postgres unique constraint on `(user_id, event_id)` is the hard correctness guarantee - it holds even if two requests race past the Redis gate or if Redis is temporarily unavailable.

### Consequences

* Good - counter increments don't block on a relational row lock.
* Good - Redis is already justified by short-lived caches (map queries) and distributed locks, the atomic counter, and the idempotency gate.
* Good - reliability ASR is satisfied by reconciliation, not by trusting Redis alone.
* Bad - two systems of record for the count during the event window. Reconciliation must be designed and tested.
* Bad - Redis is a single point of failure unless ElastiCache replication is configured. If Redis loses data, we reconcile from the Postgres rows - degraded but correct.

### Confirmation

* RSVP toggle is keyed by `(user_id, event_id)` with a unique constraint, making the underlying row idempotent under retry.
* RSVP service writes `SET NX EX 86400` on the idempotency key before opening a transaction; a key collision returns `200 OK` without a DB round-trip.
* A reconciliation job (nightly, or on demand) compares Redis counter to `SELECT COUNT(*) FROM rsvps WHERE event_id = ?` and corrects drift.
* Reliability tests in `api/src/tickettailor/rsvp/tests/test_rsvp_reliability.py` assert no drift after a concurrent burst and that induced drift is corrected from the rows.

### Failure mode

If Redis is unreachable during the event window: the `SET NX EX` gate is skipped, writes go directly to Postgres, and the unique constraint enforces idempotency. Performance suffers; correctness is preserved.

## Pros and Cons of the Options

### (a) Postgres row lock

* Good - single system of record. Trivial to reason about.
* Bad - row contention dominates under burst.
* Bad - fails the scalability ASR's headline scenario.

### (b) Redis counter + reconciliation

* Good - high throughput, atomic.
* Good - Redis is independently justified.
* Bad - two systems; reconciliation must be tested.

### (c) Count on read

* Good - no counter to maintain.
* Bad - `COUNT(*)` over RSVP rows under burst load is expensive.
* Bad - caching the result re-introduces the consistency problem.

## Implementation notes

* **2026-06-02 - counter implemented; idempotency gate deferred.** The Redis
  `INCR`/`DECR` live counter with read-through DB seeding and graceful
  degradation (DB-count fallback when Redis is unreachable) is implemented in
  `shared/redis.py` and wired into `rsvp/service.py`. The **`SET NX EX`
  idempotency gate described above is NOT yet implemented**, for two reasons:
  (1) as specified it is not cleared on cancel, so a re-RSVP within the 24 h TTL
  would be silently dropped; (2) returning the current count on a collision
  conflicts with the `/events/{id}/rsvp` contract, which returns `409` on a
  duplicate. The Postgres unique constraint on `(user_id, event_id)` plus an
  existence check remain the hard correctness guarantee in the meantime. A
  follow-up should refine the gate (clear on cancel; reconcile the 200-vs-409
  contract) before relying on it. Verified by the FR3 counter row in
  [`../../docs/traceability.md`](../../docs/traceability.md).
* **2026-06-03 - reconciliation implemented; concurrent-retry idempotency
  hardened.** `RsvpService.reconcile_event` / `reconcile_all` (the on-demand
  reconciliation job named above) now recompute the count from PostgreSQL and
  overwrite a drifted counter (`RsvpCounter.overwrite` / `scan_event_ids` in
  `shared/redis.py`). Separately, a concurrent duplicate RSVP that loses the
  `(user_id, event_id)` unique-constraint race is now translated to the same
  `409` as a serial duplicate instead of surfacing a `500`, so a retried toggle
  is idempotent-safe. Increment runs only after a successful insert, so the
  losing request never double-counts. Covered by the QA3-idempotent /
  QA3-replica / QA3-reconcile rows in
  [`../../docs/traceability.md`](../../docs/traceability.md).

## More Information

* Related ADRs: ADR-0006 (outbox/fan-out - how RSVP changes propagate to the worker), ADR-0008 (reliability tactics - read replica, reconciliation).
