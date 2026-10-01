import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Header

from tickettailor.shared.config import settings
from tickettailor.shared.exceptions import InvalidTokenError

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        _ph.verify(hashed_password, plain_password)
        return True
    except VerifyMismatchError:
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    """Mint a short-lived signed access token (ADR-0009: ~15 min, HS256)."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID:
    """Verify an access token's signature/expiry and return the subject id.

    Raises InvalidTokenError for any failure (bad signature, expiry, wrong
    type, malformed subject) so callers never have to branch on JWT internals.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError() from exc

    if payload.get("type") != "access":
        raise InvalidTokenError()

    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise InvalidTokenError()
    try:
        return uuid.UUID(sub)
    except ValueError as exc:
        raise InvalidTokenError() from exc


def generate_refresh_token() -> str:
    """A high-entropy opaque refresh token (not a JWT)."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Deterministic digest for storing/looking up a refresh token.

    SHA-256 is appropriate here (unlike passwords) because the input is a
    256-bit random secret, not a low-entropy human password.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def require_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    """FastAPI dependency: resolve the caller's user id from the bearer token.

    Lives in `shared` (not `auth`) so every module's routers can authenticate
    without importing the `auth` package, which the import-linter layer
    contract forbids. See ADR-0014.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise InvalidTokenError()
    token = authorization.removeprefix("Bearer ")
    return decode_access_token(token)


def optional_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> uuid.UUID | None:
    """Like :func:`require_current_user_id`, but returns ``None`` for anonymous
    callers instead of raising 401.

    Used by the public-browse endpoints (GET /events list, map, and detail): a
    signed-in caller is identified so they also see their club-only events,
    while an anonymous caller sees only public events. A missing *or* invalid
    token is treated as anonymous rather than a 401, so a public browse never
    errors on a logged-out visitor or a stale/expired access token. The
    per-event visibility check (EventService) is what actually withholds
    club-only events from anonymous callers - this dependency only resolves
    identity.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ")
    try:
        return decode_access_token(token)
    except InvalidTokenError:
        return None
