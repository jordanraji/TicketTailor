# syntax=docker/dockerfile:1
#
# TicketTailor outbox relay image (ADR-0002 deployable #3).
#
# The relay depends on the API package via an editable path dependency
# (../api), so BOTH trees must be in the build context. Build from the repo
# root: `docker build -f relay/Dockerfile .` (the compose stack does this).
#
# The relay does NOT run migrations - the API container owns schema migration;
# the relay only reads/writes already-migrated tables.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Mirror the repo layout under /app so the editable "../api" path resolves.
COPY api /app/api
COPY relay /app/relay

WORKDIR /app/relay
# --extra sns installs boto3 for the production SNS publisher.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra sns

ENV PATH="/app/relay/.venv/bin:$PATH"

CMD ["python", "-m", "relay"]
