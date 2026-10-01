---
status: "accepted"
date: 2026-05-09
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Security posture and tactics

## Context and Problem Statement

The architecture-suitability grading clause includes "an appropriate level of security." The security/privacy ASR (QA4) names: no privilege escalation between students/committee/admin, password protection, transport security, input validation, and resistance to API abuse. We need concrete tactics so this is answered with specifics, not hand-waving.

## Decision Drivers

* Architecture-suitability rubric explicitly mentions security.
* OWASP A01 (broken access control) is the most common cause of catastrophic failure in social platforms - students should not be able to mutate other clubs' events.
* Time budget - security must be designed in, not retrofitted.
* Privacy: TicketTailor handles location data; that has obvious sensitivity.

## Considered Options

This ADR is largely a checklist; the alternatives are between specific tactics where they exist.

## Decision Outcome

Chosen tactics:

### Authentication

* Short-lived access tokens (~15 minutes), rotating refresh tokens.
* Password hashing with **argon2id** (memory-hard; current best practice). Not bcrypt - argon2 is preferred where available.
* Refresh tokens stored as `httpOnly` + `Secure` + `SameSite=strict` cookies. Access tokens in memory only - never `localStorage`.

### Authorisation

* Role-based: `student`, `committee_member`, `admin`.
* Checks live in the **service layer**, not routers, so they're testable in isolation.
* Cross-module ownership checks via `organisers.is_member_of(user_id, club_id)` - the `events` module never reaches into organiser data.

### Transport

* TLS everywhere. ALB terminates TLS, certs via the cloud certificate manager.
* HSTS header on all responses.
* HTTPS-only cookies.

### Input validation

* Pydantic v2 strict mode (or equivalent) on every request body.
* Reject unknown fields.
* Allow-list sortable and filterable fields - never interpolate user input into `ORDER BY`.

### Injection defence

* Parameterised queries only. No raw SQL with f-strings.
* Geo functions called via ORM bindings, not string-interpolated.
* No `dangerouslySetInnerHTML` (or framework equivalent) in the frontend.

### Privacy

* Profile visibility settings: public / club-only / private.
* Event discovery is public: `GET /events` (list and geo-radius map) and `GET /events/{id}` authenticate *optionally* (`optional_current_user_id`) so a logged-out visitor can browse, but they return **public events only** - club-only events are withheld from anonymous and non-member callers by the service-layer visibility check (`EventService._can_view_event`), which is also what gates the authenticated case. All writes (create/update/delete) and RSVP remain authenticated. A missing or stale token is treated as anonymous rather than a 401, so public browse never errors.
* Attendee lists not exposed to non-organisers.
* Public event coordinates rounded to ~100 m precision when displayed publicly - don't expose exact home addresses if a student creates a private event at their address.
* Soft-delete with a retention window for account deletion.

### Secrets management

* Cloud secret manager in production.
* `.env` (gitignored) locally; `.env.example` (committed) lists required keys without values.
* Never log secrets.
* Separate IAM roles per deployable unit (ECS task for API and relay, Lambda execution role for the notification worker), least-privilege policies.

### Dependency hygiene

* `pip-audit` and `npm audit` in CI.
* Dependabot (or equivalent) for updates.
* Pin versions in lock files.

### API abuse

* Rate limiting at the load balancer or via `slowapi` (or equivalent), per-IP and per-user.
* Tighter limits on auth endpoints and on the RSVP toggle endpoint (counter abuse).
* CAPTCHA on signup as a stretch goal.

### Headers

* Strict CSP.
* `X-Frame-Options: DENY`.
* `X-Content-Type-Options: nosniff`.
* HSTS.

### Audit logging

* Auth events (login, refresh, password change, role change) logged with user ID, IP, user agent, timestamp.
* The outbox carries an `audit` category for security-relevant events.

### Testing

* `schemathesis` fuzzing the OpenAPI for input-validation gaps.
* `bandit` SAST in CI (or equivalent for the chosen language).
* `pip-audit` and `npm audit` in CI.
* One OWASP Top 10 category exercised manually per release. **A01 broken access control** first - explicitly test that a student cannot edit a club's events.
* Manual review of auth flows documented in the test report.

### Trade-offs documented

* **argon2id is slower than bcrypt.** Intentional. The DoS surface is mitigated by login rate limiting.
* **Short access token TTL increases refresh traffic.** Acceptable - refresh is cheap, and short TTLs limit token-leak blast radius.
* **Cross-module membership check is synchronous.** Acceptable in the monolith. Becomes an HTTP call if `organisers` is extracted; documented in [`../../docs/extension-paths.md`](../../docs/extension-paths.md).

## Consequences

* Good - every clause in QA4 has a named tactic.
* Good - the architecture-suitability rubric's security clause is answered with specifics.
* Bad - argon2id increases login CPU; rate limiting is doing real load-bearing work.

### Confirmation

* CI gates: `pip-audit`, `npm audit`, `bandit`, `mypy --strict`, `tsc --strict`, `schemathesis`.
* Authorisation tests at the service layer, not just the router layer.
* `tests/api/organisers/test_authz_create_event.py` covers OWASP A01.

## Pros and Cons of the Options

The tactics above were chosen against named alternatives:

* **argon2id over bcrypt.** Argon2 is the modern recommendation; bcrypt is acceptable but second-best.
* **Service-layer authz over router-layer authz.** Service-layer checks are testable in isolation and survive router refactors.
* **Standards over custom auth.** OAuth-based external auth was considered for users; it adds surface for limited gain. Local username/password is simpler and adequate for this user base.

## More Information

* OWASP Top 10: https://owasp.org/www-project-top-ten/
* Argon2: https://datatracker.ietf.org/doc/html/rfc9106
* Privacy considerations are tracked alongside FR1 and FR2 acceptance criteria in [`../../docs/architecture-overview.md`](../../docs/architecture-overview.md).
