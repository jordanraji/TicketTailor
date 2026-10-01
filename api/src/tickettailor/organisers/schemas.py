import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from tickettailor.organisers.models import MembershipRole
from tickettailor.shared.validation import StrictTextModel

schema_config = ConfigDict(from_attributes=True)
request_config = ConfigDict(extra="forbid")


class ClubCreate(StrictTextModel):
    model_config = request_config

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique name of the club",
    )
    description: str | None = Field(
        None,
        max_length=1000,
        description="Optional detailed description of the club",
    )


class ClubUpdate(StrictTextModel):
    model_config = request_config

    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Optional new name of the club",
    )
    description: str | None = Field(
        None,
        max_length=1000,
        description="Optional new description of the club",
    )


class ClubResponse(BaseModel):
    model_config = schema_config

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime


class ClubWithMembershipResponse(BaseModel):
    model_config = schema_config

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    user_role: MembershipRole


# To avoid namespace collision on MembershipRole inside Pydantic parsing
MappedRole = MembershipRole


class ClubMembershipCreate(StrictTextModel):
    model_config = request_config

    user_id: uuid.UUID = Field(
        ...,
        description="UUID of the user to assign membership to",
    )
    role: MappedRole = Field(
        MembershipRole.committee_member,
        description="Role assigned inside the club (committee_member or admin)",
    )


class ClubMembershipResponse(BaseModel):
    model_config = schema_config

    id: uuid.UUID
    user_id: uuid.UUID
    club_id: uuid.UUID
    role: MembershipRole
    created_at: datetime
