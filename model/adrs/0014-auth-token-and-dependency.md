---
status: "accepted"
date: 2026-05-31
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Token-based auth: verification in `shared`, flows in `auth`, identity via dependency

## Context and Problem Statement

ADR-0009 mandates short-lived access tokens + rotating refresh tokens with
argon2id password hashing, and says authorisation checks live in the service
layer. It does not say *where in the codebase* token verification lives, nor
how a router obtains the authenticated user. The import-linter layer contract
(`api/.importlinter`) orders the modules `… > auth > users > shared`: a higher
layer may import a lower one, never the reverse. So **no module's routers may
import `auth`** - yet every module needs to authenticate requests. The merged
`users` module worked around this with a mock `get_current_user_id` inlined in
`users/routers.py` that treats the bearer token as a raw UUID. We need a real
mechanism that respects the layer contract.

## Decision Drivers

* Layer contract: routers in `users`, `events`, `rsvp`, etc. cannot import `auth`.
* ADR-0009: argon2id, ~15-min access tokens, rotating refresh tokens.
* Testability: authorisation must be verifiable at the service layer.
* Avoid framework footguns (Starlette `BaseHTTPMiddleware` request-state
  propagation is version-sensitive).

## Considered Options

* **A - Shared verification + FastAPI dependency.** JWT mint/verify and the
  argon2 helpers live in `shared/security.py`; a `require_current_user_id`
  dependency (also in `shared`) reads and verifies the bearer token. The `auth`
  module owns the register/login/refresh/logout flows and refresh-token
  persistence.
* **B - Auth middleware sets `request.state.user_id`.** An `AuthMiddleware` in
  `auth`, registered in `main.py`, decodes the token and stores the id on
  request state; routers read the state. Matches the wording in
  architecture-overview ("consumed via auth middleware").
* **C - Reorder the layer contract** so `auth` sits below `users`, letting the
  dependency live in `auth`. Inverts the real semantic dependency (auth's
  `register` delegates to `users`).

## Decision Outcome

Chosen option: **A**. Token verification and password hashing are placed in
`shared/security.py`, exposed through a `require_current_user_id` FastAPI
dependency that every module's routers can use without importing `auth`. The
`auth` module owns the credential/token *flows* (`AuthService`) and refresh
token storage; its `register` delegates to `users.UserService` (permitted:
`auth` is above `users`).

Option B was rejected because `BaseHTTPMiddleware` request-state propagation
has historically been brittle across Starlette versions, and per-route
dependency verification is explicit and unit-testable. Option C was rejected
because reordering the contract to suit a utility's location inverts the real
dependency direction and risks legitimising future cross-module reaches.

### Consequences

* Good - every module authenticates uniformly via one shared dependency; the
  layer contract is preserved with no exceptions.
* Good - verification is explicit per route and trivially testable.
* Good - token type, expiry, and rotation are centralised in `shared/security`.
* Neutral - diverges from architecture-overview's "middleware" wording; the
  overview is updated to say "shared dependency" and reference this ADR.
* Bad - the `users` module still carries its mock `get_current_user_id`. A
  follow-up (coordinated with the module owner) replaces it with
  `require_current_user_id` and deletes the mock. Tracked, not silently left.

### Confirmation

* `api/.importlinter` stays green (no router imports `auth`).
* `auth/tests/test_auth_flow.py` covers signup → login → authenticated `/auth/me`
  → 401 without credentials, wrong-password rejection, and refresh rotation
  (FR1, QA4-authz rows in `docs/traceability.md`).

## More Information

* Refresh tokens are opaque high-entropy strings (`secrets.token_urlsafe`),
  stored as a SHA-256 digest (deterministic lookup; the input is not a
  low-entropy password so argon2 is unnecessary). Access tokens are HS256 JWTs.
* Relates to [ADR-0009](0009-security-tactics.md) (security tactics).
* Follow-up: swap the `users` mock identity dependency; see the team note.
