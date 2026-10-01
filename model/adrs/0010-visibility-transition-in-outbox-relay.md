---
status: "accepted"
date: 2026-05-17
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Visibility transition folded into the outbox relay

## Context and Problem Statement

ADR-0002 introduced a third deployable - a scheduled-task lambda (`lambdas/visibility_cron/`) that fires every 5 minutes to flip club-only events public at their `transition_at` time and publish `visibility_changed` events (FR5). The Outbox Relay (ADR-0006) is already a continuously running process whose work loop - find rows, mutate state, publish events - is structurally identical. This ADR decides whether the scheduled visibility transition warrants its own deployable or should fold into the relay.

## Decision Drivers

* Cost concern raised in team review (small in absolute terms, but real signal that the deployable wasn't justified).
* Deployable count - three deployables (API + notification worker + outbox relay) is the framing ADR-0002 commits to. Adding a fourth deployable that doesn't earn its keep weakens the architecture-evaluation story.
* Avoid introducing new technology - the relay already exists in the design; folding work into it adds no new runtime, language, or operational surface.
* Reliability ASR (QA3) - the merged design must preserve at-least-once delivery and tolerate concurrent relay replicas.
* Scheduling resolution - the relay's poll interval (seconds) is finer-grained than the previous 5-minute cron, which is acceptable but worth naming.

## Considered Options

* (a) Keep the visibility cron as a separate Lambda + EventBridge rule (the status quo per ADR-0002).
* (b) Fold the scheduled visibility transition into the Outbox Relay.
* (c) Run the visibility transition as a background `asyncio` task inside the API container.
* (d) Use an ECS Scheduled Task (EventBridge → Fargate one-shot) in place of Lambda.

## Decision Outcome

Chosen option: **(b) fold into the Outbox Relay**, because it removes one deployable without sacrificing correctness, introduces no new technology, and preserves the "three deployable units" framing of ADR-0002.

Each relay tick now performs two queries:

1. **Scheduled visibility transition** - `UPDATE events SET visibility = 'public' WHERE visibility = 'club_only' AND transition_at <= now() RETURNING id`, and for each returned row, insert a `visibility_changed` domain event into the `outbox` table within the same transaction.
2. **Outbox publish** (unchanged) - `SELECT ... FROM outbox WHERE published_at IS NULL FOR UPDATE SKIP LOCKED`, publish to SNS, mark rows as published.

The two queries run in sequence within the same tick. `FOR UPDATE SKIP LOCKED` semantics on both queries keep multiple relay replicas safe.

### Consequences

* Good - one fewer deployable to test, document, operate, and defend. Three units (API, notification worker, outbox relay), each with a clear single-sentence justification.
* Good - scheduling resolution improves from 5 minutes (cron granularity) to the relay's poll interval (seconds). FR5 latency story tightens.
* Good - `visibility_changed` events flow through the same outbox → SNS → SQS pipeline as every other domain event. One reliability test covers the whole path.
* Bad - the relay's responsibility grows from "publish events" to "publish events + run scheduled DB mutations." If the scheduled-mutation list grows beyond visibility transitions, the relay's job description will drift.
* Bad - coupling: a bug in the scheduled-mutation query could starve the outbox publish loop on the same tick. Mitigate with independent error handling and separate metrics per phase.

### Confirmation

* Tests covering FR5 live under `relay/tests/` (e.g. `test_visibility_transition.py`), not `lambdas/`. They assert: (i) events with `transition_at <= now()` flip to public, (ii) a `visibility_changed` outbox row is written in the same transaction, (iii) the relay's normal publish path picks it up and SNS receives it.
* Multiple relay replicas running concurrently produce no double-flip and no duplicate `visibility_changed` events (reliability test).
* `lambdas/visibility_cron/` is removed from the tree; the L2 diagram has no Visibility Cron container; the deployables list in `architecture-overview.md` lists three units.

## Pros and Cons of the Options

### (a) Keep the Lambda

* Good - strongest separation of concerns: each deployable does one thing.
* Good - Lambda + EventBridge cron is genuinely cheap (free-tier territory for this workload).
* Bad - adds a fourth deployable that doesn't earn its keep. The architecture-evaluation grade values *justified* complexity, not maximal separation.
* Bad - duplicates Terraform, IAM, and observability surface for a small amount of code.

### (b) Fold into the Outbox Relay

* Good - eliminates a deployable. Three units, each justified by an ASR.
* Good - no new technology.
* Good - finer scheduling resolution.
* Bad - broadens the relay's responsibility. Needs to be explicit in docs and ADR-0006.
* Bad - coupling risk between the scheduled-mutation query and the outbox publish loop. Mitigable.

### (c) Background `asyncio` task inside the API

* Good - zero additional infra.
* Bad - every API replica would run the scheduled task unless leader election or DB locking is added.
* Bad - couples scheduling concerns into the request-handling process; complicates the API's failure modes.
* Bad - weakens the "API does request handling only" story that the modular-monolith narrative depends on.

### (d) ECS Scheduled Task

* Good - keeps separation of concerns.
* Bad - Fargate task startup cost on every fire is *more* expensive than Lambda, not less. Solves nothing for the cost concern that triggered this ADR.

## More Information

Amends ADR-0002 (deployables list) and ADR-0006 (relay scope); both were `proposed` at the time so they were edited in place rather than superseded. Revisit if the relay's scheduled-mutation list grows beyond visibility transitions - at that point the relay may warrant being renamed or split.
