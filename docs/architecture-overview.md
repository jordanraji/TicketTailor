# Architecture overview

Team-facing description of TicketTailor's architecture. Suitable for onboarding a new team member or for the marker reading the report alongside the code.

**Status note.** ADRs 0001-0018 have been accepted by the team (0004 superseded by 0018).

## What we are building

TicketTailor is a university social-events platform. Students discover events on a geo-filtered interactive map, RSVP, follow clubs and societies, and receive real-time notifications when events change or transition from club-only to public. Committee members create and manage events, configure pricing (free vs. ticketed) and visibility (private vs. public), and trigger time-offset visibility transitions.

Final submission: whatever is on `main` at 15:00 on 8 June 2026.

## Functional requirements (MVP)

| ID | Requirement | Acceptance criterion (testable) |
| --- | --- | --- |
| FR1 | Authentication and user profiles with club affiliations | A new user can sign up, log in, set descriptive metadata, and join a club. Authenticated requests return 200 for the user's own profile and 401 without credentials. |
| FR2 | Interactive map with geo-filter (radius) and interest-category filter | Given an event seeded at coordinate X, a map query within R km of X returns it; outside R km it does not. Combined with category filter, only matching events are returned. |
| FR3 | RSVP with persisted aggregate count, correct under concurrent load | After N concurrent toggles by N distinct users, the persisted count equals the number of users currently in the "going" state. No double-counting; idempotent under retry. |
| FR4 | Organiser tools: create event with pricing flag and visibility flag | A committee member can create a free or ticketed event, marked private or public. Non-organisers cannot. |
| FR5 | Time-offset transition club-only → public, with broad-base notification | At the configured offset, the visibility flag flips and a notification is fanned out to every user following the organising club. The transition is observable in the audit log. |
| FR6 | Save to calendar (iCal export, optional OAuth integration) | An RFC 5545 iCal feed is generated for the event and validates against an iCal validator. Round-trip into Google/Outlook/Apple Calendar preserves title, time, location, description (manual conformance test). |
| FR7 | Organiser edit → real-time push to RSVP'd attendees | When an organiser edits an event, every RSVP'd attendee receives a web push notification acked by the browser's push service within the FR7 SLO (p95 ≤ 5 s, p99 ≤ 10 s; see [ADR-0011](../model/adrs/0011-web-push-via-vapid.md)). |

The "broader user base" in FR5 is defined as the set of users following the organising club. The "real-time" SLO for FR7 is decided in [ADR-0011](../model/adrs/0011-web-push-via-vapid.md).

## Quality attributes (graded ASRs)

For each, we name: definition in this project's context, the architecturally significant requirement (concrete and measurable), the tactic, and the row(s) in [`traceability.md`](traceability.md) that prove it.

### QA1 - Scalability

**Definition.** Sustained correctness and acceptable latency under spike load, particularly when a popular private event flips to public and triggers a notification fan-out.

**ASR.** Given an event with **N = 1,000** followers and the platform serving **M = 50 requests/sec** of concurrent map queries, a club-only → public flip must complete fan-out to all N followers with **p95 ≤ 30 s and p99 ≤ 60 s** of notification ack at the worker; concurrent map-query **p99 ≤ 500 ms**; RSVP-toggle **p99 ≤ 200 ms**; error rate **< 1 %**. These numbers are the headline targets for the load test in [`traceability.md`](traceability.md). The executed run to date demonstrated **N = 300** (300/300 delivered, fan-out p95 = 5.1 s - roughly 6x headroom under the 30 s SLO); scaling to the N = 1,000 target is argued by extrapolation, since ack latency stayed flat as N grew 15x (20 -> 300) - see [`test-reports/load-test-2026-06-06.md`](test-reports/load-test-2026-06-06.md).

**Tactics.**
- Extract the notification worker into a separate process so it scales independently of the API.
- Asynchronous fan-out via a message queue with topic-based subscription, decoupling publish from delivery.
- Read replica(s) for the geo-query path so map traffic doesn't compete with writes.
- An atomic counter store (Redis or equivalent) for the live RSVP count, avoiding row-lock contention.
- Auto-scaling on API and worker tiers, exercised by the load test.

**Traceability.** Rows QA1-* in [`traceability.md`](traceability.md).

### QA2 - Interoperability

**Definition.** Event metadata flows correctly into Google Calendar, Outlook, and Apple Calendar via standard formats - the user adds the event once and sees it in their calendar of choice with title, time, location, and description preserved.

**ASR.** Given an event with title, geographic coordinates, start/end timestamps, and description, an iCal feed generated by the system parses without errors against an RFC 5545 validator and round-trips correctly through each of the three target calendars.

**Tactics.**
- iCal (RFC 5545) export and webcal subscription URL by default - standards conformance, not vendor integration.
- Optional OAuth-based two-way sync as a stretch goal (ADR-0007).

**Traceability.** Rows QA2-* in [`traceability.md`](traceability.md).

### QA3 - Reliability

**Definition.** Event and attendee data stay consistent across replicas during high-frequency updates. RSVP counts and event-status changes don't drift, even under load and partial failure.

**ASR.** Under sustained RSVP churn during a load test, the persisted aggregate count and individual RSVP rows agree after reconciliation, with no drift attributable to lost messages, double-counting, or replication lag. Surviving a single replica failure mid-burst does not corrupt the count.

**Tactics.**
- Idempotent RSVP writes - unique constraint on `(user_id, event_id)`.
- Transactional outbox pattern for cross-process events: domain event written in the same transaction as the business write; a relay publishes to the message queue.
- Periodic reconciliation comparing the live counter to the persisted RSVP rows.
- Read-replica failover, exercised in a reliability test.

**Traceability.** Rows QA3-* in [`traceability.md`](traceability.md).

### QA4 - Privacy and security

**Definition.** Authenticated users can do only what their role permits; their data is protected in transit and at rest; the system resists common API abuse.

**ASR.** No authenticated student can mutate events for clubs they are not a committee member of (OWASP A01). Auth tokens are short-lived; passwords are hashed with a memory-hard function. Input validation rejects malformed bodies; rate limiting prevents counter abuse.

**Tactics.** Detailed in ADR-0009. Authentication via short-lived access tokens + rotating refresh tokens; argon2id for password hashing; role-based authorisation in the service layer; TLS everywhere; Pydantic-style strict validation; rate limiting per IP and per user.

**Traceability.** Rows QA4-* in [`traceability.md`](traceability.md).

## Architecture overview (C4 Levels 1 and 2)

This architecture deliberately sits between a 2-tier site and full microservices.

The shape we are proposing:

- **Three deployable units.** A modular-monolith API, a notification worker extracted from it, and an outbox relay that publishes domain events to SNS and runs the scheduled FR5 visibility transition (see ADR-0010).
- **Three datastore concerns.** A relational primary store with geo-extension support, a fast counter/cache, and a publish-subscribe message bus.
- **One frontend.** A single-page web app served from object storage behind a CDN.
- **External systems.** Calendar providers (consumed via iCal), a push provider, an email provider, and a map-tile provider (OpenStreetMap, loaded client-side for the FR2 map; ADR-0019).

Why not a 2-tier site: there are three deployable processes, three data stores, and an explicit asynchronous boundary - meaningfully more sophisticated than "FastAPI + Postgres."

Why not full microservices: four independently deployed services dramatically expand the testing surface and operational load for a student team. With 65% of the grade on testing, architecture description, and architecture evaluation, surface complexity hurts more than it helps. The module boundaries inside the monolith are *enforceable* - separate packages, separate database schemas, no cross-module imports - which means the report can credibly argue for a per-module extraction path. That argument is the answer to the "expandable to a larger system" criterion. See [`extension-paths.md`](extension-paths.md).

The C4 diagrams under [`../model/artefacts/c4/`](../model/artefacts/c4/) describe the system context (Level 1), containers (Level 2), and the Backend API's internal components (Level 3).

## Bounded contexts and module layout

| Module | Owns | Internal interface | Consumed by |
| --- | --- | --- | --- |
| `auth` | credentials, tokens, password records | `authenticate`, `issue_tokens`, `rotate_refresh` | every router via the shared `require_current_user_id` dependency (ADR-0014); public event browse uses the `optional_current_user_id` variant (anonymous → public events only, ADR-0009) |
| `users` | user profile, club follows, push subscriptions | `get_profile`, `update_profile`, `clubs_for_user`, `followers_for_club`, `contact_details_for` | `events`, `organisers`, `rsvp`, `outbox_relay` |
| `events` | event records, geo-coords, visibility state | `search_events`, `get_event`, `create_event`, `transition_visibility` | `rsvp`, `calendar`, frontend |
| `rsvp` | RSVP rows, aggregate counter | `toggle_rsvp`, `count_for_event`, `attendees_for_event` | `events`, frontend, `outbox_relay` |
| `organisers` | committee membership, ownership policy | `is_member_of`, `can_edit_event` | `events`, `rsvp` |
| `calendar` | iCal generation, optional OAuth sync | `ical_for_event`, `ical_feed_for_user` | frontend |
| (extracted) `notifications` worker | push and email delivery | consumes from message queue topics | - |
| (extracted) `outbox_relay` | publishes outbox rows; runs scheduled FR5 visibility transition; hydrates + fans out per-recipient notifications (ADR-0016) | reads/writes `events`, `outbox`; reads `users` (followers, contacts) and `rsvp` (attendees) to hydrate; publishes per-recipient messages to SNS | - |

**Module-talk rule.** Modules talk only through their service interface; no direct repository or model imports across modules. Enforced by an automated boundary check in CI plus code review. If an import-linter contract isn't viable in the chosen language, an equivalent must be agreed and added before any cross-module code is written.

## Cross-cutting concerns

- **Authentication.** Short-lived access tokens (~15 min) plus rotating refresh tokens. Argon2id for password hashing (memory-hard; current best practice). Refresh tokens stored as `httpOnly`, `Secure`, `SameSite=strict` cookies. Access tokens in memory only - never `localStorage`.
- **Authorisation.** Role-based: `student`, `committee_member`, `admin`. Checks live in the service layer, not routers, so they're testable in isolation. Cross-module ownership checks via `organisers.is_member_of` rather than reaching into organiser data.
- **Logging.** Structured JSON, correlation ID propagated via middleware and into queue messages. No secrets or PII in log lines.
- **Metrics and tracing.** Application metrics emitted to the chosen platform; OpenTelemetry tracing as a stretch goal.
- **Configuration.** Environment variables. Secrets in the cloud secret manager in production; `.env` (gitignored) plus `.env.example` (committed) locally.
- **Errors.** `application/problem+json` responses. Stack traces logged, never returned.
- **Input validation.** Strict schemas on every request body (Pydantic v2 strict mode in Python; equivalent elsewhere). Reject unknown fields. Allow-list sortable/filterable fields to avoid SQL injection through `ORDER BY`.
- **Rate limiting.** At the load balancer or via an in-process limiter. Per-IP and per-user limits; tighter limits on auth endpoints and on RSVP toggle.
- **Headers.** Strict CSP, `X-Frame-Options`, `X-Content-Type-Options`, HSTS via API middleware.

## Tech stack (accepted via ADRs)

These are the selected technologies, finalized by accepting the relevant ADRs.

- Backend: Python 3.12 + FastAPI + SQLAlchemy 2 async + Pydantic v2 + asyncpg (ADR-0003).
- Frontend: Next.js (App Router) + React + Tailwind, built to a static bundle via `output: 'export'` (ADR-0018, superseding ADR-0004). JavaScript for now, TypeScript migration deferred. Map library: MapLibre GL JS with OpenStreetMap raster tiles (ADR-0019).
- Datastore: PostgreSQL with PostGIS, with at least one read replica (ADR-0008).
- Counter/cache: Redis (ElastiCache) for `INCR`/`DECR` and short-lived caches (ADR-0005).
- Async messaging: AWS SNS → SQS fan-out, with a transactional outbox in the primary store (ADR-0006).
- Calendar interop: RFC 5545 iCal export (ADR-0007).
- Web push: native Web Push Protocol with VAPID via `pywebpush` (ADR-0011).
- Email: Resend in prod, Mailpit catcher in dev and CI ([ADR-0012](../model/adrs/0012-email-provider-resend.md)).
- Cloud target: AWS (ECS Fargate for API and outbox relay; AWS Lambda for notification worker triggered by SQS Event Source Mapping; RDS for primary; ElastiCache for counter; S3 + CloudFront for the frontend). Pending team confirmation.
- IaC: Terraform 1.x with shared state per the CSSE6400 collaboration guide.
- Local dev: Docker Compose; LocalStack or equivalent for AWS services; Mailpit for outbound email.
- CI: GitHub Actions.

## Local development

The local stack is defined in [`../docker-compose.yml`](../docker-compose.yml): PostgreSQL+PostGIS, Redis, and a Mailpit SMTP sink, plus the API itself. From the repository root, `docker compose up --build` starts the dependencies, waits for the database, applies all module migrations, and serves the API on `http://localhost:8000` (Mailpit UI on `http://localhost:8025`). Integration tests run against a throwaway PostGIS container via testcontainers - `cd api && uv run pytest`. Seeded test data and the local load-test target are still to come.

## Testing strategy

- **Unit.** Per-module, ≥70 % coverage on domain logic.
- **Integration.** Real database and counter store via testcontainers (or equivalent); a fake/local message queue for fan-out.
- **Module-boundary.** Automated check in CI fails if any module imports across boundaries.
- **Contract.** Schemathesis (or equivalent) against the OpenAPI spec.
- **End-to-end.** Playwright-driven happy-path flows.
- **Load.** k6 or Locust; the headline scenario is "private event flips public, fan-out to N users."
- **Reliability.** Kill the primary database mid-burst, observe failover; kill the worker mid-fanout, assert messages are redelivered; reconcile counter vs. persisted RSVP rows.
- **Security smoke.** SAST (`bandit` or equivalent), `pip-audit` and `npm audit` in CI, schemathesis fuzzing of the OpenAPI for input-validation gaps.
- **iCal conformance.** Validate generated feeds against an RFC 5545 validator; manual round-trip through Google/Outlook/Apple Calendar documented in the test report.

Headline numbers are set in the QA1 ASR above and mirrored in [`traceability.md`](traceability.md): N=1,000 follower fan-out, M=50 RPS sustained map traffic, fan-out p95 ≤ 30 s / p99 ≤ 60 s, map p99 ≤ 500 ms, RSVP p99 ≤ 200 ms, error rate < 1 %. The N=1,000 fan-out is the target; the executed run demonstrated N=300 (300/300 delivered, p95 = 5.1 s) and argues the 1,000 target by extrapolation (ack latency stayed flat as N grew 15x, 20 -> 300) - see [`test-reports/load-test-2026-06-06.md`](test-reports/load-test-2026-06-06.md).

## Deployment

Cloud target proposed: AWS. Three deployable units: API and outbox relay as separate ECS Fargate task definitions with independent auto-scaling, notification worker as AWS Lambda triggered by SQS Event Source Mapping, RDS for the primary store with at least one read replica, ElastiCache for the counter, SNS topic + SQS notifications queue, S3 + CloudFront for the frontend, ALB in front of the API. Terraform under [`../infra/`](../infra/), one workspace per environment (`dev`, `prod`).

**Realised on AWS Academy Learner Lab** ([ADR-0017](../model/adrs/0017-learner-lab-deployment-profile.md), accepted). The counter runs on managed **ElastiCache** as specified above - an early assumption that the lab forbade ElastiCache was tested with a throwaway probe and disproven, so no substitution is needed there. The lab's constraints do force two substitutions that preserve every tactic: all roles reference the pre-provisioned `LabRole` (no custom IAM), and ingress uses the ALB / CloudFront default domains (no ACM custom domain). The Terraform in [`../infra/`](../infra/) implements this profile; its [README](../infra/README.md) is the apply/destroy runbook. A full AWS account would revert the remaining substitutions with no change to module boundaries.

## CI/CD

GitHub Actions. Jobs: lint, type-check, module-boundary, tests, container build and push, `terraform plan` on PRs, report PDF build on changes to [`../report/`](../report/).

## Architectural decision log

Maintained in [`../model/adrs/`](../model/adrs/). One-line summary table:

| ADR | Title | Status |
| --- | --- | --- |
| 0001 | Record architectural decisions | accepted |
| 0002 | Modular monolith with extracted notification worker | accepted |
| 0003 | Backend language and framework | accepted |
| 0004 | Frontend framework and SPA-only | superseded by 0018 |
| 0005 | Atomic counter store for RSVP | accepted |
| 0006 | Async fan-out with transactional outbox | accepted |
| 0007 | iCal export by default; OAuth two-way sync as stretch | accepted |
| 0008 | Read replica plus reliability tactics | accepted |
| 0009 | Security posture | accepted |
| 0010 | Visibility transition folded into the outbox relay | accepted |
| 0011 | Web push delivery via VAPID, no third-party push service | accepted |
| 0012 | Email provider: Resend in prod, Mailpit in dev and test | accepted |
| 0013 | Decoupled per-module database migrations | accepted |
| 0014 | Token auth: verification in `shared`, flows in `auth`, identity via dependency | accepted |
| 0015 | Cross-module validation via shared callbacks | accepted |
| 0016 | Relay-side notification fan-out with hydrated messages | accepted |
| 0017 | Learner Lab deployment profile | accepted |
| 0018 | Frontend framework: Next.js with static export (supersedes 0004) | accepted |

Update this table when an ADR's status changes.

## Known risks and open questions

- Load-test environment cost - `terraform destroy` after every run.
- OAuth scope creep on calendar sync - keep iCal as default; OAuth is stretch only.
- Marker performance with thousands of pins - clustering strategy on the map.
- Module boundaries decay if not enforced - automated check in CI is non-negotiable.
- Resend sandbox-mode recipients - without a verified domain the demo can only send to addresses team members have verified (see [ADR-0012](../model/adrs/0012-email-provider-resend.md)).
- Outbox relay transition scan - the relay polls `events WHERE visibility='club_only' AND transition_at <= now()` every tick (default 1 s). This is now backed by the partial index `idx_events_transition_scan` on `(transition_at) WHERE visibility='club_only'` (events migration `c4a9e1f2b3d5`), so the scan is proportional to the pending-transition set rather than the whole table. The relay's publish query is covered by `idx_outbox_unpublished`.

## Out of scope

- Real payments. The pricing flag controls UI presentation only; no payment integration.
- Native iOS/Android apps.
- Apple Push specifically - web push and email only.
- ML-based recommendations.
- Two-way calendar sync (export only, unless the OAuth stretch goal is reached).
- In-app chat.

## Definition of done for the MVP

- [ ] All seven FRs deliver their acceptance criteria; each has at least one passing test in [`traceability.md`](traceability.md).
- [ ] Each ASR has a passing test (or a documented manual conformance test for QA2).
- [ ] CI is green: lint, type-check, module-boundary, tests.
- [ ] Architecture diagrams in [`../model/artefacts/c4/`](../model/artefacts/c4/) reflect the deployed system.
- [ ] All proposed ADRs are accepted, rejected, or superseded - none lingering as `proposed`.
- [ ] Demo video recorded; link in [`../demo.md`](../demo.md).
- [ ] Report builds via CI to a PDF and is up to date with the code.

## Glossary

- **ADR** - Architectural Decision Record. One per significant decision.
- **ASR** - Architecturally Significant Requirement. The graded quality attributes, made concrete.
- **MADR** - Markdown Any Decision Records - the ADR template format we use.
- **iCal / RFC 5545** - calendar interchange format.
- **Outbox pattern** - domain event written in the same DB transaction as the business write; relayed to the message bus for reliable fan-out.
- **PostGIS** - geographic extension to PostgreSQL.
- **Modular monolith** - a single deployable process with strict internal module boundaries that could be split into services later.
- **Traceability matrix** - table mapping every requirement to the test(s) that prove it.
