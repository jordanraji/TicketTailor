# Requirements traceability matrix

Every functional and quality-attribute requirement maps to the test(s) that prove it. This matrix is the canonical reference for the report's Evaluation section.

**Rule.** If a requirement has no test row, either the test is missing or the requirement is undelivered. Either is a problem to fix, not hide. When a test is added, the matrix row is updated in the same commit.

## How to read this matrix

- **Test type** - `unit`, `integration`, `contract`, `e2e`, `load`, `reliability`, `security`, `conformance`, `manual`.
- **Test path** - repository-relative path to the test file. `TODO` means the test is not yet written.
- **Status** - `planned`, `passing`, `partial`, or `failing`. `partial` means a requirement that bundles several claims met some but not all (the linked test report says which). New rows start `planned`.

## Functional requirements

| ID | Requirement | Test type | Test path | Status |
| --- | --- | --- | --- | --- |
| FR1 | Authentication and user profiles with club affiliations | integration | `api/src/tickettailor/auth/tests/test_auth_flow.py`, `api/src/tickettailor/organisers/tests/test_club_management.py` | passing |
| FR1 | Club-affiliation read/write on user profile | integration | `api/src/tickettailor/users/tests/test_profile_clubs.py` | passing |
| FR2 | Map: events within radius R from coord X (ST_DWithin, nearest-first, 50 km clamp, public-only) | integration | `api/src/tickettailor/events/tests/test_geo_search.py` | passing |
| FR2 | Map: combined geo-radius and category filter | integration | `api/src/tickettailor/events/tests/test_combined_filter.py` | passing |
| FR2 | Map UI renders (OpenStreetMap tiles via MapLibre GL JS, ADR-0019) and plots geo-radius results in the browser | e2e | `tests/e2e/specs/events-map.spec.ts` | passing |
| FR3 | RSVP toggle is idempotent under retry (incl. concurrent retry → 409, never double-count) | reliability | `api/src/tickettailor/rsvp/tests/test_rsvp_reliability.py::test_concurrent_duplicate_rsvp_is_idempotent` | passing |
| FR3 | Aggregate count correct under concurrent toggles | reliability | `api/src/tickettailor/rsvp/tests/test_rsvp_reliability.py::test_concurrent_distinct_rsvps_no_counter_drift` | passing |
| FR3 | Redis counter tracks going-state across place/cancel and seeds from DB on cold cache (ADR-0005) | integration | `api/src/tickettailor/rsvp/tests/test_rsvp.py` | passing |
| FR4 | Committee can create event with pricing flag and visibility flag | integration | `api/src/tickettailor/events/tests/test_event_creation.py` | passing |
| FR4 | Non-organiser cannot create or mutate club events (outsider + cross-tenant organiser, OWASP A01) | security | `api/src/tickettailor/events/tests/test_event_authz.py`, `api/src/tickettailor/events/tests/test_event_creation.py`, `api/src/tickettailor/events/tests/test_event_crud.py` | passing |
| FR5 | Visibility transition club-only → public at offset | integration | `relay/tests/test_visibility_transition.py` | passing |
| FR5 | Outbox publish pass: unpublished rows published once, at-least-once on failure (ADR-0006) | integration | `relay/tests/test_fanout.py`, `relay/tests/test_visibility_transition.py` | passing |
| FR5 | Notification fan-out on visibility flip | integration | `worker/tests/test_visibility_fanout.py` | passing |
| FR6 | iCal feed parses against RFC 5545 validator (re-parse, required props, escaping round-trip, 75-octet folding) | conformance | `api/src/tickettailor/calendar/tests/test_ical_conformance.py` | passing |
| FR6 | Round-trip through Google/Outlook/Apple Calendar (Google manually confirmed 2026-06-06: escaping + timezone; Outlook/Apple via RFC 5545 conformance; subscribe path on the deployed stack) | manual | `docs/test-reports/calendar-roundtrip.md` | passing |
| FR7 | Organiser edit pushes notification to RSVP'd attendees | integration | `worker/tests/test_organiser_edit_push.py` | passing |
| FR7 | Push ack within p95 ≤ 5 s, p99 ≤ 10 s (ADR-0011); demonstrated N=300: p95 4.6 s, p99 4.8 s, 300/300 delivered (worker-ack boundary) | load | `tests/load/scenarios/organiser_edit.js`, `docs/test-reports/fr7-push-ack-2026-06-07.md` | passing |

## Quality attributes

| ID | Requirement | Test type | Test path | Status |
| --- | --- | --- | --- | --- |
| QA1-load | Spike: private event flips public, fan-out within p95 ≤ 30 s, p99 ≤ 60 s. Target N=1,000; demonstrated N=300 (300/300 delivered, p95 = 5.1 s), 1,000 argued by extrapolation (ack flat as N grew 15x, 20 -> 300) | load | `tests/load/scenarios/visibility_spike.js`, `docs/test-reports/load-test-2026-06-06.md` | passing |
| QA1-scale | API and worker auto-scale: RSVP p99 ≤ 200 ms under M=50 RPS sustained, error rate < 1 % | load | `tests/load/scenarios/sustained_rsvp.js`, `docs/test-reports/load-test-2026-06-06.md` | partial |
| QA1-replica | Map p99 ≤ 500 ms under M=50 RPS sustained traffic | load | `tests/load/scenarios/map_traffic.js`, `docs/test-reports/load-test-2026-06-06.md` | passing |
| QA2-ical | iCal output validates against RFC 5545 validator | conformance | `api/src/tickettailor/calendar/tests/test_ical_conformance.py` | passing |
| QA2-roundtrip | Round-trip through Google/Outlook/Apple Calendar (Google manually confirmed 2026-06-06: escaping + timezone; Outlook/Apple via RFC 5545 conformance; subscribe path on the deployed stack) | manual | `docs/test-reports/calendar-roundtrip.md` | passing |
| QA3-idempotent | RSVP toggle idempotent under retry | reliability | `api/src/tickettailor/rsvp/tests/test_rsvp_reliability.py::test_concurrent_duplicate_rsvp_is_idempotent` | passing |
| QA3-replica | RSVP count drift across replicas during burst | reliability | `api/src/tickettailor/rsvp/tests/test_rsvp_reliability.py::test_concurrent_distinct_rsvps_no_counter_drift` | passing |
| QA3-failover | Primary failover mid-burst preserves count (in-process analogue: primary unreachable mid-burst -> in-flight writes rejected, no phantom count, full recovery on retry) | reliability | `api/src/tickettailor/rsvp/tests/test_failover.py::test_primary_failover_midburst_preserves_count` | passing |
| QA3-outbox | Relay interrupted mid-fan-out: unpublished rows redelivered next tick; at-least-once deduplicable by stable id (ADR-0006). Cross-process SQS→Lambda redelivery deferred to load-test infra | reliability | `relay/tests/test_redelivery.py` | passing |
| QA3-redelivery | Worker reports SQS partial-batch failures so only failed messages redeliver (at-least-once); a transient channel failure re-raises for redelivery while an expired push subscription is swallowed | reliability | `worker/tests/test_lambda_handler.py::test_lambda_handler_partial_batch_failure`, `...::test_process_domain_event_reraises_on_transient_channel_failure`, `...::test_process_domain_event_swallows_expired_subscription` | passing |
| QA3-reconcile | Counter vs. persisted rows reconcile to zero drift; induced drift corrected from DB | reliability | `api/src/tickettailor/rsvp/tests/test_rsvp_reliability.py::test_reconciliation_corrects_induced_drift`, `...::test_reconcile_all_sweeps_every_live_counter` | passing |
| QA4-authz | Student cannot mutate other clubs' events (OWASP A01): cross-tenant organiser of club A blocked from B's events | security | `api/src/tickettailor/events/tests/test_event_authz.py` | passing |
| QA4-authn | Unauthenticated requests are rejected; bad/expired tokens give 401 | integration | `api/src/tickettailor/auth/tests/test_auth_flow.py` | passing |
| QA4-input | Schemathesis fuzzing finds no input-validation gaps (no input yields a 5xx); NUL/surrogate text rejected at the boundary | security | `api/src/tickettailor/tests/test_schemathesis.py`, `api/src/tickettailor/tests/test_text_input_validation.py` | passing |
| QA4-deps | `pip-audit` clean in CI (npm audit deferred until `web/` exists) | security | `.github/workflows/security.yml` | passing |
| QA4-sast | `bandit` SAST clean in CI | security | `.github/workflows/security.yml` | passing |

## Architectural rules

| ID | Rule | Test type | Test path | Status |
| --- | --- | --- | --- | --- |
| AR1 | No cross-module imports inside the API | unit | `api/.importlinter` (import-linter layers contract, run in CI and pre-commit) | passing |
| AR2 | OpenAPI spec is the contract; clients validate against it (schemathesis generates from the spec; full response-schema conformance still deferred) | contract | `api/src/tickettailor/tests/test_schemathesis.py` | passing |
| AR3 | E2E happy path: signup → RSVP → calendar, plus the FR7 push precondition (attendee joins the recipient set; delivery itself proven by `worker/tests/test_organiser_edit_push.py` + the `organiser_edit.js` load test) | e2e | `tests/e2e/specs/happy-path.spec.ts` | passing |
