import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

# Callback signature: (db_session, club_id) -> True if exists, else False
ClubValidatorCallable = Callable[[AsyncSession, uuid.UUID], Awaitable[bool]]

_validator: ClubValidatorCallable | None = None


def register_club_validator(validator: ClubValidatorCallable) -> None:
    """Register the club validator callback from the organisers module."""
    global _validator
    _validator = validator


async def validate_club_exists(db: AsyncSession, club_id: uuid.UUID) -> bool:
    """Check if a club exists using the registered validator.

    Raises RuntimeError if the validator callback is not registered,
    enforcing a fail-fast integration policy.
    """
    if _validator is None:
        raise RuntimeError("Club validator callback has not been registered.")
    return await _validator(db, club_id)
