"""Boundary input-validation shared across request schemas.

PostgreSQL text columns cannot store a NUL (0x00) byte, and asyncpg cannot encode
an unpaired UTF-16 surrogate to send to the server; either reaches the driver (or
argon2 when hashing a password) as an unhandled error and surfaces to the caller
as a 500. ``StrictTextModel`` rejects both at the API boundary so such inputs
fail as a clean 422 instead. The gap was found by the QA4-input schemathesis
fuzzing (a NUL byte in a free-text field); see docs/traceability.md.
"""

from typing import Self

from pydantic import BaseModel, model_validator


def reject_unstorable_text(value: str) -> str:
    """Raise ``ValueError`` if ``value`` is text the datastore cannot persist.

    NUL (0x00) bytes are not storable in a Postgres text column, and an unpaired
    UTF-16 surrogate cannot be encoded to UTF-8 for the asyncpg wire; either
    would otherwise surface as a 500. Returns the value unchanged when storable,
    so it doubles as a Pydantic ``AfterValidator`` for query params (where a
    ``ValueError`` becomes a clean 422).
    """
    if "\x00" in value:
        raise ValueError("text must not contain NUL (0x00) characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("text must be valid UTF-8 (no unpaired surrogates)") from exc
    return value


def reject_unstorable_text_optional(value: str | None) -> str | None:
    """``reject_unstorable_text`` that passes ``None`` through (optional params)."""
    if value is None:
        return None
    return reject_unstorable_text(value)


class StrictTextModel(BaseModel):
    """Base for request models: reject text the datastore cannot persist.

    Applied to every string field on the model (including optional ones once
    present), so new request fields are covered without per-field annotation.
    """

    @model_validator(mode="after")
    def _reject_unstorable_text(self) -> Self:
        for value in self.__dict__.values():
            if isinstance(value, str):
                reject_unstorable_text(value)
        return self
