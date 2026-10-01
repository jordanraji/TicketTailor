# Outbox relay

A standalone deployable (ADR-0002, unit #3) whose poll loop runs two phases per
tick, each in its own transaction (ADR-0010):

1. **Scheduled visibility transition (FR5)** - flips club-only events whose
   `transition_at` has passed to public, writing a `visibility_changed` row to
   the outbox in the same transaction.
2. **Outbox publish (ADR-0006)** - drains unpublished `shared.outbox` rows and
   publishes them to the message bus (SNS in prod).

Both phases use `FOR UPDATE SKIP LOCKED`, so multiple relay replicas run safely
with no double-flip and no duplicate publish.

## Layout

| Path | What it is |
| --- | --- |
| `src/relay/service.py` | `OutboxRelay` - the two-phase tick (`run_visibility_transition`, `publish_pending`, `tick`) |
| `src/relay/publisher.py` | `Publisher` protocol + `LoggingPublisher` (dev), `CollectingPublisher` (tests), `SnsPublisher` (prod) |
| `src/relay/loop.py` | the long-running poll loop + process wiring (engine, publisher selection, signal handling) |
| `src/relay/config.py` | `RelayConfig` - DB/SNS from the shared API settings; poll cadence and batch sizes from env |
| `tests/` | integration tests against a real PostGIS container (testcontainers) |

The relay reuses the API's SQLAlchemy models and DB plumbing via an editable
path dependency on `../api` - single source of truth for the `events` and
`shared.outbox` table shapes. It never runs migrations; the API owns those.

## Running

Locally via the compose stack (uses the logging publisher - no SNS topic):

```bash
docker compose up --build       # from the repo root; starts db, cache, api, relay
```

Standalone (against a reachable database):

```bash
cd relay
uv sync
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tickettailor \
  uv run python -m relay
```

Set `AWS_SNS_TOPIC_ARN` (and install the `sns` extra: `uv sync --extra sns`) to
publish to SNS instead of logging.

### Configuration

| Env var | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | local dev URL | primary store (shared with the API) |
| `RELAY_POLL_INTERVAL_SECONDS` | `1.0` | seconds between ticks |
| `RELAY_PUBLISH_BATCH_SIZE` | `100` | max outbox rows published per tick |
| `RELAY_TRANSITION_BATCH_SIZE` | `100` | max events flipped per tick |
| `AWS_SNS_TOPIC_ARN` | unset | SNS topic; when unset the relay logs instead of publishing |
| `AWS_REGION` | `ap-southeast-2` | SNS region |

## Tests

```bash
cd relay
uv run pytest          # spins up a throwaway PostGIS container via testcontainers
uv run ruff check
uv run mypy -p relay
```

Tests cover the FR5 transition (flip + same-transaction outbox row, idempotency,
concurrent-replica safety) and the ADR-0006 publish pass (publish + stamp, skip
already-published, batch size, dedup key, at-least-once on bus failure).
