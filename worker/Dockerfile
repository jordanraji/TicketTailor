# syntax=docker/dockerfile:1
#
# TicketTailor notification worker - container-image Lambda (ADR-0002 #2,
# ADR-0016). Triggered by the per-channel SQS queues; delivery only, no DB.
#
# Build from the worker/ directory: `docker build -t tickettailor-worker .`
#
# Two stages: uv resolves and installs the package + deps into a venv, then the
# site-packages are copied onto the AWS Lambda Python base image (which provides
# the Runtime Interface Client). The handler is worker.lambda_handler.lambda_handler.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# --no-editable so the `worker` package is copied into site-packages (not a .pth
# pointing at /app/src, which does not exist in the final image).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM public.ecr.aws/lambda/python:3.12

COPY --from=build /app/.venv/lib/python3.12/site-packages ${LAMBDA_TASK_ROOT}

CMD ["worker.lambda_handler.lambda_handler"]
