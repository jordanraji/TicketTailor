#!/bin/sh
# Apply all module migrations, then exec the container command (the API server).
# Compose waits for the database healthcheck before starting this container, so
# the database is reachable by the time migrations run.
set -e

echo "==> Applying database migrations"
python -m tickettailor.shared.migrate upgrade

echo "==> Starting: $*"
exec "$@"
