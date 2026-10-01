---
status: "accepted"
date: 2026-05-30
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Web push delivery via VAPID, no third-party push service

## Context and Problem Statement

FR7 requires real-time push notifications to RSVP'd attendees when an organiser edits an event, and FR5 fans notifications out on a club-only → public visibility flip. [ADR-0004](0004-spa-frontend.md) commits to web push only - no native iOS/Android, no Apple Push. The L1/L2 C4 diagrams show a "Web Push Provider" external system but did not name a concrete provider, and the SLO for "real-time" was an open question.

The choice is whether to integrate a hosted push platform (Firebase Cloud Messaging, AWS SNS Mobile Push) or speak the W3C Web Push Protocol directly using VAPID-signed messages to the browser-supplied push endpoints that the Push API hands out.

## Decision Drivers

* Web-push-only scope is locked by [ADR-0004](0004-spa-frontend.md) and the architecture overview's "out of scope" list.
* No additional cloud account, SDK, or paid tier - this is a 9-day student capstone.
* The notification worker is an AWS Lambda triggered by SQS Event Source Mapping ([ADR-0002](0002-modular-monolith-with-extracted-worker.md), [ADR-0010](0010-visibility-transition-in-outbox-relay.md)); whatever we pick must fit in the Lambda runtime cleanly.
* The FR7 SLO must be measurable in the load test (QA1).
* No vendor lock-in for a feature the marker will see for two minutes.

## Considered Options

* **Native Web Push via VAPID** - `pywebpush` in the Lambda worker signs payloads with the team's VAPID keypair and POSTs to the browser-supplied push endpoint. The browser's push service (FCM / Mozilla autopush / Apple Push) handles last-mile delivery.
* **Firebase Cloud Messaging (FCM) web SDK** - set up a Firebase project, integrate the FCM SDK in the SPA, register tokens with the API, send via FCM REST from the worker.
* **AWS SNS Mobile Push (web platform)** - register browser endpoints as SNS platform endpoints; the worker publishes through SNS topics.

## Decision Outcome

Chosen option: **Native Web Push via VAPID**, because it requires zero additional vendor accounts, no extra cloud credentials in the demo, no SDK weight in the SPA bundle, and matches the worker's existing AWS Lambda shape with a single `pywebpush` call.

The FR7 SLO is **p95 of notifications acked by the browser's push service within 5 seconds** of the trigger event, **p99 within 10 seconds**. "Ack" is measured at the worker - the HTTP response from the push endpoint indicates the push service accepted the message. Actual browser-side receipt is outside our control and is verified manually in the demo, not in the load test.

### Consequences

* Good - no third-party push platform to provision, manage, or pay for. The only new secret is the VAPID private key.
* Good - the SPA needs only the W3C Push API plus a service worker. No FCM/Firebase SDK in the bundle.
* Good - the worker stays cleanly modular: it takes a `PushSubscription` row from the DB and POSTs to its endpoint. Adapter pattern is trivial.
* Bad - VAPID private key must be rotated manually; no managed rotation.
* Bad - error semantics differ between push services (FCM / Mozilla / Apple): the worker must handle `410 Gone` (expired subscription, delete from DB) and `429 Too Many Requests` (back off).

### Confirmation

* `push_subscriptions` table in the primary DB stores `endpoint`, `p256dh`, `auth` per subscribed user.
* `pywebpush` pinned in the worker's dependency manifest.
* VAPID keypair stored in AWS Secrets Manager in prod; in `.env` (gitignored) locally. Public key delivered to the SPA via a `GET /push/vapid-public-key` endpoint.
* Integration test in `worker/tests/test_web_push.py` asserts a successful POST to a stub push endpoint, and that a `410 Gone` triggers subscription deletion.
* Load test `tests/load/scenarios/visibility_spike.js` measures worker-side fan-out latency and asserts p95 ≤ 5 s, p99 ≤ 10 s.

## Pros and Cons of the Options

### Native Web Push via VAPID

* Good - no vendor lock-in, no extra account, no extra cost.
* Good - adapter in the worker is small and testable.
* Bad - operator handles VAPID key rotation manually.

### Firebase Cloud Messaging

* Good - managed, with delivery analytics.
* Bad - Firebase project setup, Google account dependency, an extra SDK and config file in the SPA.
* Bad - vendor lock-in for a feature with no business case for the lock-in.

### AWS SNS Mobile Push (web)

* Good - same cloud account as the rest of the infrastructure.
* Bad - more wiring than VAPID for no real benefit; SNS platform endpoints add an indirection.
* Bad - historically less well-documented for web push than for native mobile.

## More Information

* [ADR-0004](0004-spa-frontend.md) - SPA framework and the web-push-only scope.
* [ADR-0010](0010-visibility-transition-in-outbox-relay.md) - visibility transition fans out via the same worker.
* [`../../docs/architecture-overview.md`](../../docs/architecture-overview.md) - FR7 acceptance criterion and QA1 ASR.
