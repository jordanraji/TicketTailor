---
status: "accepted"
date: 2026-05-09
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Modular monolith with extracted notification worker

## Context and Problem Statement

Course staff guidance is that microservices is not mandated, but a simple monolith or 2-tier website is unlikely to be suitable: the system must be sophisticated enough to deliver within the time constraints and credibly expandable to a larger system. We need an architectural shape that:

1. Is meaningfully more sophisticated than a 2-tier site.
2. Avoids the operational and testing surface of full microservices, given a student team and the grading weights (testing + architecture description + evaluation = 65%).
3. Is credibly *expandable* to a larger system, so the report's Critique and Evaluation sections have a real story to tell.
4. Demonstrably exercises the three graded ASRs (scalability, interoperability, reliability).

## Decision Drivers

* Scalability ASR - must demonstrably handle a private→public flip with notification fan-out, with auto-scaling.
* Reliability ASR - RSVP counts and event-status changes consistent across replicas during high-frequency updates.
* Interoperability ASR - calendar export to Google/Outlook/Apple.
* Time budget - 14-week semester, student team.
* Grading weights - testing (20%), architecture description (25%), architecture evaluation (20%) sum to 65%; surface complexity hurts there more than it helps.
* "Expandable to a larger system" criterion (architecture-suitability, 15%).

## Considered Options

* (a) Traditional 2-tier - a single web app + a relational database.
* (b) Full microservices - API gateway + four or more independently deployed services + a worker.
* (c) Modular monolith with extracted notification worker and outbox relay.

## Decision Outcome

Chosen option: **(c) modular monolith with extracted notification worker and outbox relay**, because it is meaningfully more sophisticated than a 2-tier site (three deployable units, three datastore concerns, an explicit asynchronous boundary), keeps the testing and operational surface manageable for a student team, and - through enforced module boundaries - gives a credible per-module extraction story for the "expandable" criterion.

The outbox relay also runs scheduled domain mutations (currently the FR5 visibility transition); see ADR-0010.

### Consequences

* Good - three deployable units (API, notification worker, outbox relay), three datastore concerns (relational, counter/cache, message bus), one async boundary. Comfortably above "2-tier site."
* Good - one API process means the testing surface is bounded. We can run real integration tests against the whole API in one container.
* Good - the worker is extracted because the scalability ASR demands it (independent scaling on the fan-out path), not as ceremony. Easy to defend in the report.
* Good - the notification worker on Lambda scales to zero when idle and scales concurrency automatically with queue depth, with no polling overhead or idle compute cost.
* Good - module boundaries inside the API are *enforceable* (separate packages, separate database schemas, automated boundary check in CI). The report can credibly argue per-module extraction paths - see [`../../docs/extension-paths.md`](../../docs/extension-paths.md).
* Bad - discipline burden. A modular monolith only works if the boundary check is enforced. Any PR that breaches it must be blocked.
* Bad - Lambda has a maximum execution timeout (15 minutes). If a notification batch is very large, the worker must process within this window or implement chunking. For the expected scale of this project this is not a concern.
* Bad - extracting later (if we ever need to) is still real engineering work, even if the boundaries make it cheap relative to a tangled monolith.

### Confirmation

* Module-boundary check (import-linter or equivalent) running in CI, blocking PRs that breach.
* Each module under `api/src/tickettailor/<module>/` with its own routers, services, repositories, models - and its own database schema.
* The notification worker lives under `worker/`, with its own deployment unit (AWS Lambda, triggered by SQS Event Source Mapping).
* The outbox relay lives under `relay/`, with its own deployment unit. It publishes outbox rows to SNS and runs scheduled domain mutations (see ADR-0010).

## Pros and Cons of the Options

### (a) 2-tier

* Good - fastest to build.
* Bad - course staff have explicitly said it's unlikely to be suitable.
* Bad - no obvious place to demonstrate the scalability ASR (fan-out under load).
* Bad - no extraction story.

### (b) Full microservices

* Good - maximally "expandable" by construction.
* Good - clear boundaries between services.
* Bad - operational and testing surface explodes. Four services × integration tests + contract tests + per-service deploys + per-service observability. Eats the time we need for testing quality (20%).
* Bad - the course staff guidance says microservices is *not mandated*. Choosing it imposes cost we can't justify against the grading rubric.

### (c) Modular monolith with extracted worker

* Good - sits between (a) and (b) in sophistication; the course staff guidance points here.
* Good - one extraction (the worker) is justified by the scalability ASR; further extractions are documented as paths but not built.
* Good - the notification worker on Lambda is a natural fit for event-driven, bursty workloads - no idle compute, automatic scaling with queue depth.
* Good - the report has a strong narrative: "we extracted what the ASRs demanded, and we have a credible extraction path for everything else."
* Bad - relies on enforced module boundaries. Without the CI check, this collapses to a tangled monolith and the extraction story becomes a lie.
* Bad - Lambda's 15-minute timeout must be respected in the worker implementation.

## More Information

* [`../../docs/architecture-overview.md`](../../docs/architecture-overview.md) - the prose description.
* [`../../docs/extension-paths.md`](../../docs/extension-paths.md) - per-module extraction stories.
* [`../../docs/traceability.md`](../../docs/traceability.md) - proof.
* Revisit if a load test reveals a hot spot whose extraction is not in [`extension-paths.md`](../../docs/extension-paths.md).
