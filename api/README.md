# TicketTailor API

Core backend for CSSE6400 TicketTailor project. It's a modular monolith running on FastAPI.

## Getting Started

Make sure you have Python 3.12+ and `uv` installed. If you don't have `uv` yet, check out their install guide [here](https://astral.sh/uv).

### Set up your local dev env

1. Jump into this folder and sync up the dependencies:
   ```bash
   uv sync
   ```
2. Copy the template env file:
   ```bash
   cp .env.example .env
   ```
   Open up `.env` and tweak your local Postgres and Redis database details if needed.
3. Install the pre-commit hooks to run the API CI pipeline locally on every commit:
   ```bash
   uv run pre-commit install --config ../.pre-commit-config.yaml
   ```

### Quickstart with Docker Compose (recommended)

The whole local stack - PostgreSQL+PostGIS, Redis, and a Mailpit SMTP sink - is
defined in [`../docker-compose.yml`](../docker-compose.yml). From the repository
root:

```bash
docker compose up --build
```

This starts the dependencies, waits for the database to be healthy, runs all
migrations, and serves the API. Then:

*   API - http://localhost:8000 (Swagger at `/docs`, health at `/healthz`)
*   Mailpit web UI - http://localhost:8025

Tear down with `docker compose down` (add `-v` to also drop the database volume).

### Manual setup (without Docker)

Because the events schema uses geospatial features, your PostgreSQL instance **must have PostGIS installed**. For installation guidelines, see the [PostGIS Documentation](https://postgis.net).

Once your PostgreSQL database is running and PostGIS is enabled, execute the following command to run all database migrations:

```bash
uv run python -m tickettailor.shared.migrate upgrade
```

You can verify the current migration version of each module by running:

```bash
uv run python -m tickettailor.shared.migrate current
```

## Running the API locally

To spin up the local server with auto-reload:

```bash
uv run uvicorn tickettailor.main:app --reload
```

Once it's running, you can:
*   Hit `http://127.0.0.1:8000/healthz` to check the health check.
*   Head to `http://127.0.0.1:8000/docs` to play around with the Swagger UI docs.

## Code Quality & CI Checks

Please run these checks before pushing to your branch so we don't break the CI pipeline.

*   **Check modular boundaries (Import Linter)**:
    ```bash
    uv run lint-imports
    ```
*   **Run linter & formatter (Ruff)**:
    ```bash
    uv run ruff check --fix
    ```
*   **Strict type checks (Mypy)**:
    ```bash
    uv run mypy -p tickettailor
    ```
*   **Run the test suite (Pytest)**:
    ```bash
    uv run pytest
    ```
