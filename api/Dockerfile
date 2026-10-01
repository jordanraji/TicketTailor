# syntax=docker/dockerfile:1
#
# TicketTailor API image. uv-based, installs the project editable so that
# `tickettailor.shared.migrate` resolves its per-module alembic.ini paths
# relative to /app/src at runtime (see migrate.py).

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Resolve dependencies first so this layer is cached unless the lockfile
#    changes. --no-install-project: the app itself is installed in step 2.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# 2. Install the application (editable, into /app/.venv).
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
# Shell form so ${UVICORN_WORKERS} expands at runtime (the entrypoint execs
# this via `sh -c`). A single uvicorn process only uses one core; run one
# worker per vCPU in the task. Pool sizing in config is per-process, so keep
# UVICORN_WORKERS * (DB_POOL_SIZE + DB_MAX_OVERFLOW) within the RDS budget.
CMD uvicorn tickettailor.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}
