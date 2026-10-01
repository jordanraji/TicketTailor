---
status: "accepted"
date: 2026-05-31
decision-makers: [TicketTailor team]
consulted: []
informed: []
---

# Decoupled database migrations using module-scoped Alembic environments

## Context and Problem Statement

As established in [ADR-0002](0002-modular-monolith-with-extracted-worker.md), our backend is designed as a modular monolith to keep the architecture clean and make it credibly expandable to a larger system. To support this decoupled architectural pattern at the database layer, each module must own its own isolated tables and PostgreSQL schema, with no physical cross-schema foreign key constraints.

The question then arises of how to manage database schema migrations. A single global Alembic setup would couple the modules' schema histories together, violating the modularity constraint and complicating any future extraction of modules (e.g., `events` or `users`) into separate microservices. We need a migration strategy that keeps each module's database migrations completely isolated and independent.

## Decision Drivers

*   Modular Monolith boundary constraint (AR1, [ADR-0002](0002-modular-monolith-with-extracted-worker.md)) - no cross-module coupling at the database or migration level.
*   "Expandable to a larger system" suitability criterion - extracting a module into an independent service must be clean and cheap.
*   Ease of local development - developers must be able to run a single command to migrate all local database schemas.
*   PostGIS geospatial indexing requirement in the `events` module.

## Considered Options

*   **Option 1: Single global Alembic environment** - All schemas and tables are managed within a single Alembic migration sequence and history table in the `public` schema.
*   **Option 2: Decoupled Alembic environments per module with a unified orchestration runner** - Each module (`users`, `auth`, `organisers`, `events`, `rsvp`, `calendar`, `shared`) maintains its own self-contained Alembic configuration, migration scripts, and its own schema-scoped version tracking table (`alembic_version`). An orchestrator script handles running migrations sequentially for local development.

## Decision Outcome

Chosen option: **Option 2: Decoupled Alembic environments per module with a unified orchestration runner**, because it enforces strict boundaries at the data layer, guarantees that migration histories are fully isolated per module, and allows any module to be extracted into a separate service without decoupling migration scripts.

To document the database design and sequence flows, we utilize:
*   [tickettailor_schema.dbml](../artefacts/erd/tickettailor_schema.dbml) as the official Entity-Relationship Diagram representing the schemas and their logical cross-module references.
*   D2-based C4 diagrams and sequence diagrams to model the architectural components and transaction boundaries.

### Consequences

*   Good - True database decoupling. Modules can be moved to separate physical database instances in the future without modification to their migration histories.
*   Good - Strong boundary enforcement. A migration script in one module cannot inadvertently reference or alter tables in another module.
*   Good - Clean database schema isolation using dedicated PostgreSQL schemas (`users`, `organisers`, `events`, `rsvp`, `calendar`, `auth`, `shared`).
*   Bad - Operational setup overhead. We have to maintain separate `alembic.ini` and `env.py` files for each module, resulting in some duplication of boilerplate migration configuration.
*   Bad - Autogeneration limitation. Alembic's `revision --autogenerate` needs to connect to the database to inspect tables. It must be run against the specific module's target schema, which requires local database setups to have the PostGIS extension enabled (for the events module).

### Confirmation

*   Isolated `alembic.ini` configurations and `migrations/` directories under each module directory `api/src/tickettailor/<module>/`.
*   Separate migration version tracking tables configured inside each schema: `version_table_schema` set to the module's schema name, and `version_table` set to `alembic_version`.
*   Orchestration script in `api/src/tickettailor/shared/migrate.py` that imports and runs Alembic commands sequentially.
*   The import linter (`import-linter lint`) validates that module boundaries are kept clean in Python.

## Pros and Cons of the Options

### Option 1: Single global Alembic environment

*   Good - Simple configuration. Only one `alembic.ini` and one `migrations/` directory to manage.
*   Good - Easy out-of-the-box migrations.
*   Bad - Monolithic data coupling. Migration scripts will interlace different modules' schemas, making it very difficult to extract a module in the future.
*   Bad - High risk of boundary violations. It is easy for a developer to write a migration that creates physical foreign keys or cross-schema dependencies.

### Option 2: Decoupled Alembic environments per module with a unified orchestration runner

*   Good - Absolute decoupling. Zero shared state between module migrations.
*   Good - Future-proof. Aligning database separation with application separation directly supports the modular monolith's long-term extensibility goals.
*   Bad - Boilerplate duplication across the 7 modules' migration configurations.

## More Information

*   [ADR-0002: Modular monolith with extracted notification worker](0002-modular-monolith-with-extracted-worker.md)
*   [Database Migrations Orchestration Script](../../api/src/tickettailor/shared/migrate.py)
*   [DBML Database Schema Representation](../artefacts/erd/tickettailor_schema.dbml)
