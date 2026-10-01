---
status: "accepted"
date: 2026-06-01
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Cross-module validation via shared callbacks

## Context and Problem Statement

The modular monolith layer contract (enforced via `api/.importlinter`) defines the package hierarchy:
`calendar > rsvp > events > organisers > auth > users > shared`
A higher layer may import from a lower layer, but lower layers must never import from higher ones to avoid circular dependencies and tight coupling.

Under this architecture, the lower-level `users` module needs to validate club references when a user follows a club (i.e. `follow_club` and `unfollow_club`). However, the `organisers` module, which owns the definition and database queries for clubs, is located at a higher level than `users`.
Consequently, the `users` module cannot import any classes, services, or functions from the `organisers` module without violating the layer contract.
We need a clean, decoupled mechanism for the `users` module (and potential future lower-level modules) to perform validations that require access to data or logic owned by higher-level modules.

## Decision Drivers

* **Modular layer contract adherence**: The dependency direction must respect `organisers > users > shared` with zero imports from `organisers` inside `users`.
* **Coupling minimization**: Avoid direct compilation or runtime imports between sibling/lower modules that introduce high coupling.
* **Fail-fast integration**: Misconfigurations or missing registrations of cross-module components must be detected immediately at runtime, rather than failing silently or assuming valid state (falling open).
* **Testability**: The design must allow unit and integration testing without requiring complex setups or heavy mocks.

## Considered Options

* **A - Shared Callback Registry (Dependency Inversion).** Create a validator interface with a callable signature in the `shared` layer (which all modules can import). The higher-level module (`organisers`) registers its concrete validation function into this registry at application startup/import time. The lower-level module (`users`) imports and invokes the validator from the `shared` layer. If the registry is not initialized, it raises a `RuntimeError` (fail-fast policy).
* **B - Shared/Duplicate Database Queries.** The `users` module performs raw SQL queries or repository operations against the `clubs` table directly.
* **C - Synchronous REST / Internal HTTP calls.** Pretend modules are microservices and have `users` make an HTTP call to a `/clubs` endpoint.

## Decision Outcome

Chosen option: **A (Shared Callback Registry)**, because it strictly adheres to the layer contract while maintaining a single source of truth for business logic (owned by `organisers`). 

Option B was rejected because it violates module boundaries, duplicates schema knowledge (e.g. `users` needs to know about `organisers.models.Club`), and bypasses the domain logic layer of the owning module.
Option C was rejected because it introduces unnecessary overhead, network serialization costs, and complexity into a single-process deployment.

### Consequences

* Good - Enforces the layer contract: `users` does not import `organisers`.
* Good - Logic ownership: `organisers` remains the single source of truth for club existence logic (`ClubService`).
* Good - Fail-fast: The system raises `RuntimeError` immediately if an attempt is made to use the validator before it is registered (e.g., during tests or partial imports), avoiding silent failures.
* Bad - Introduces a global mutable state registry in `shared` that is set via side effect during module loading/startup.

### Confirmation

* Import linter checks (`api/.importlinter`) pass, validating that no illegal imports are made.
* Integration tests in `users/tests/test_profile_clubs.py` and `organisers/tests/test_club_management.py` verify that follower and membership logic execute correctly under this mechanism.

## Pros and Cons of the Options

### Option A - Shared Callback Registry (Dependency Inversion)

* Good - Zero direct dependencies between `users` and `organisers`.
* Good - Easy to mock/stub in unit tests (simply register a dummy callback in `conftest.py`).
* Good - Enforces fail-fast behavior: if `main.py` fails to register the callback, calls to it raise a clear `RuntimeError`.
* Bad - Relies on runtime setup in `main.py` or global registration side-effects.

### Option B - Shared/Duplicate Database Queries

* Good - Avoids runtime registrations or side effects.
* Bad - Severe violation of modular boundaries. Any schema changes in the `organisers` module would break the `users` module.
* Bad - Bypasses any business rules (e.g. checking soft-deletions or visibility) that the `organisers` service might enforce.

### Option C - Synchronous REST / Internal HTTP calls

* Good - Mimics a microservices architecture, preparing modules for future extraction.
* Bad - Severe performance penalty and serialisation overhead.
* Bad - Requires mock HTTP server setups for simple unit tests.

## More Information

* The registry is implemented in [club_validator.py](../../api/src/tickettailor/shared/club_validator.py).
* Registration is done in [main.py](../../api/src/tickettailor/main.py) during startup.
* Usage is located in `follow_club` within [service.py](../../api/src/tickettailor/users/service.py).
* Relates to [ADR-0013](0013-decoupled-database-migrations.md) (no physical database foreign keys across modules).
