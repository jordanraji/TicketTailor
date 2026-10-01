# Coding conventions

Conventions that don't deserve their own ADR but that the whole team must respect. If a convention here turns out to be wrong, change it here and announce it - don't quietly drift.

**Status note.** All core decisions have been ratified. The backend stack is Python (ADR-0003) and the frontend stack is a Next.js SPA, static export (ADR-0018, which supersedes ADR-0004).

## Backend (Python)

- Type hints required on every public function and method. Use `mypy --strict` in CI.
- Async-first for all I/O - database, HTTP, message queue. Don't mix sync and async drivers in one process.
- Repository pattern between service layer and ORM. Routers are thin: parse request, call service, return response.
- No business logic in routers. No SQL in service layer. No HTTP concerns in repositories.
- Module boundaries enforced by `import-linter` (or equivalent). The contract is defined and run in CI.
- Linter: `ruff` with default plus project-specific rules. No suppressions without a `# noqa: <code> - <reason>` comment.

## Frontend (Next.js SPA, static export)

- Function components and hooks; no class components.
- Server state via a query library (TanStack Query or equivalent) - don't roll caching by hand.
- Runtime validation of API responses (Zod or equivalent). Never trust the network shape blindly.
- The frontend is JavaScript (ADR-0018); TypeScript `strict` mode is deferred, not mandated.
- Map library: MapLibre GL JS with OpenStreetMap raster tiles (ADR-0019). Avoid vendors that charge per map load.

## API design

- REST + JSON over HTTPS. No RPC, no GraphQL on the MVP.
- Errors as `application/problem+json` (RFC 7807): `type`, `title`, `status`, `detail`, optional `instance`.
- Timestamps in ISO 8601, UTC, with explicit timezone marker (`...Z`).
- Pagination via cursor - never offset, never page-number.
- HTTP status codes used for their semantic meaning, not as a catch-all.
- Idempotency keys on any endpoint with side effects that the client may legitimately retry (RSVP toggle is the obvious case).

## Git

- Conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `perf:`.
- One logical change per commit. Squash-merge unless preserving a sequence is genuinely useful.
- PR titles match conventional commit format.
- `main` is protected; PRs require one review.
- Feature branches: `<author>/<short-slug>` (e.g. `daniel/rsvp-counter`).

## Tests

- Arrange - Act - Assert. Avoid clever helpers that hide setup.
- One assertion concept per test (multiple `assert` statements are fine if they're testing the same outcome).
- Fixtures over inheritance/setup methods. Pytest fixtures should be small and composable.
- Integration tests use real databases via testcontainers or equivalent - don't mock the database driver.
- Every quality-attribute claim has a corresponding test. See [`traceability.md`](traceability.md).

## Documentation

- Markdown for everything except the report (LaTeX).
- Keep `docs/` files terse. They are reference material, not essays.
- ADRs are the durable record of *why*; READMEs say *what*.
