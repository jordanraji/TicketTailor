import asyncio
import os
import sys

import asyncpg
from alembic import command
from alembic.config import Config

# Define the order in which migrations will be executed.
# Since schemas are independent with no cross-schema physical foreign keys,
# the order is not strict, but a logical sequence aids in readability.
MODULE_CONFIGS = [
    "src/tickettailor/shared/alembic.ini",
    "src/tickettailor/users/alembic.ini",
    "src/tickettailor/auth/alembic.ini",
    "src/tickettailor/organisers/alembic.ini",
    "src/tickettailor/events/alembic.ini",
    "src/tickettailor/rsvp/alembic.ini",
    "src/tickettailor/calendar/alembic.ini",
]

# Stable arbitrary key for the migration advisory lock. Every process that
# mutates the schema takes this lock first, so concurrent container starts
# (the API service autoscales 2->N tasks, each running migrations on boot)
# serialise instead of racing Alembic against the shared database.
_MIGRATION_LOCK_KEY = 0x7173_6F72

# Commands that mutate the schema and must not run concurrently.
_MUTATING_COMMANDS = {"upgrade", "downgrade"}


def _asyncpg_dsn() -> str:
    """libpq DSN for asyncpg.connect, derived from DATABASE_URL.

    asyncpg wants a plain ``postgresql://`` DSN, not SQLAlchemy's
    ``postgresql+asyncpg://`` form.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL is not set in the environment or .env file")
    return url.replace("+asyncpg", "")


def _run_modules(cmd_name: str, *args: str) -> None:
    api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    os.chdir(api_dir)

    for ini_path in MODULE_CONFIGS:
        module_name = os.path.basename(os.path.dirname(ini_path))
        print("\n========================================================")
        print(f" Running Alembic '{cmd_name}' for module: {module_name}")
        print("========================================================")

        cfg = Config(ini_path)
        try:
            if cmd_name == "upgrade":
                target = args[0] if args else "head"
                command.upgrade(cfg, target)
            elif cmd_name == "downgrade":
                target = args[0] if args else "-1"
                command.downgrade(cfg, target)
            elif cmd_name == "current":
                command.current(cfg)
            elif cmd_name == "history":
                command.history(cfg)
            else:
                print(f"Unknown command: {cmd_name}")
                sys.exit(1)
        except Exception as e:
            print(f"Error in module {ini_path}: {e}")
            sys.exit(1)


async def _run_modules_locked(cmd_name: str, *args: str) -> None:
    """Hold a session-level advisory lock while the Alembic loop runs.

    The lock is held on a dedicated asyncpg connection in this event loop. The
    Alembic commands themselves run in a worker thread because each module's
    env.py calls ``asyncio.run`` internally, which cannot nest inside this
    loop. ``pg_advisory_lock`` blocks (it does not fail) until any other
    migrating process releases the lock, so the losers wait rather than crash.
    """
    # timeout bounds establishing the lock connection so a startup against an
    # unreachable database fails fast instead of hanging the entrypoint. It does
    # not bound the lock wait itself (pg_advisory_lock blocks until granted),
    # which is the intended serialise-don't-fail behaviour.
    conn = await asyncpg.connect(_asyncpg_dsn(), timeout=10)
    try:
        await conn.execute("SELECT pg_advisory_lock($1::bigint)", _MIGRATION_LOCK_KEY)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: _run_modules(cmd_name, *args))
    finally:
        try:
            await conn.execute(
                "SELECT pg_advisory_unlock($1::bigint)", _MIGRATION_LOCK_KEY
            )
        finally:
            await conn.close()


def run_command(cmd_name: str, *args: str) -> None:
    if cmd_name in _MUTATING_COMMANDS:
        asyncio.run(_run_modules_locked(cmd_name, *args))
    else:
        _run_modules(cmd_name, *args)


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python -m tickettailor.shared.migrate "
            "[upgrade|downgrade|current|history] [revision]"
        )
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]
    run_command(cmd, *args)


if __name__ == "__main__":
    main()
