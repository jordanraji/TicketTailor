---
status: "accepted"
date: 2026-05-09
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Backend language and framework

## Context and Problem Statement

The API is a modular monolith (ADR-0002). It must support: typed contracts, async-first I/O for the fan-out path, geo-radius queries, an automated module-boundary check, and an OpenAPI-driven contract test. The team needs to pick a language and web framework, weighing existing skills against fitness for the ASRs.

## Decision Drivers

* Async-first I/O - the scalability ASR requires non-blocking calls during the fan-out window.
* Type checking - the architecture-description grade rewards rigour; static types help.
* Geo support - the events module uses geo-radius queries.
* OpenAPI generation - needed for the contract-test ASR.
* Team familiarity.
* Strong testing ecosystem - testcontainers, schemathesis or equivalent.

## Considered Options

* Python 3.12 + FastAPI + SQLAlchemy 2.x async + Pydantic v2 + asyncpg.
* Node.js + NestJS or Fastify + Prisma or TypeORM.
* Go + chi/echo + a typed ORM (sqlc) + a typed validation layer.

## Decision Outcome

Chosen option: **Python + FastAPI**, because it gives us OpenAPI generation for free, async-first request handling, Pydantic v2 strict validation as a first-class concept, mature geo-extension support via SQLAlchemy + PostGIS, and a strong testing ecosystem (`pytest`, `testcontainers`, `schemathesis`).

This ADR locks in the backend stack across the whole project. Confirm the team is comfortable with Python before flipping to `accepted`. If the team would rather use Node or Go, this ADR moves to `superseded` and the relevant alternative is written up.

### Consequences

* Good - OpenAPI is generated from route signatures; contract tests run against it in CI.
* Good - Pydantic v2 strict mode gives us request validation without manual schema work.
* Good - `import-linter` is a mature Python tool; module-boundary enforcement is straightforward.
* Bad - Python's GIL is irrelevant for an async-first I/O-bound workload, but we should remember it if any CPU-bound work creeps into the API path (push to the worker instead).
* Bad - `mypy --strict` adds friction relative to a language with first-class types.

### Confirmation

* `mypy --strict` in CI.
* `ruff` linter in CI.
* `import-linter` contract enforcing module boundaries (ADR-0002).
* `schemathesis` running against the generated OpenAPI in CI.

## Pros and Cons of the Options

### Python + FastAPI

* Good - async-first, OpenAPI built-in, Pydantic strict mode.
* Good - strong testing ecosystem (testcontainers-python, schemathesis, pytest-asyncio).
* Good - `import-linter` for module boundaries.
* Bad - types are bolted on (`mypy --strict` required for rigour).

### Node.js + NestJS/Fastify

* Good - TypeScript types are first-class.
* Good - same language across frontend and backend if we go that way.
* Bad - geo support via PostGIS is workable but less idiomatic than in Python's SQLAlchemy.
* Bad - module-boundary enforcement requires more bespoke tooling.

### Go

* Good - first-class types, fast.
* Good - async/concurrency is idiomatic.
* Bad - slower iteration speed for a student team building an MVP.
* Bad - fewer high-level testing libraries comparable to schemathesis.

## More Information

This ADR is required input to ADR-0004 (frontend) only insofar as we want to avoid constraints that break frontend choices. Revisit if a critical capability the chosen stack lacks emerges during build.
