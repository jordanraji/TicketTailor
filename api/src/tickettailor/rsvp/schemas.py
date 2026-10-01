from pydantic import BaseModel, ConfigDict, Field

schema_config = ConfigDict(from_attributes=True)
request_config = ConfigDict(extra="forbid")


class RsvpResponse(BaseModel):
    """Response schema returned after placing or canceling an RSVP."""

    model_config = schema_config

    attendee_count: int = Field(
        ...,
        description="The updated total count of attendees for the event",
        ge=0,
    )


class RsvpStatusResponse(BaseModel):
    """Response schema indicating a user's RSVP status for a specific event."""

    model_config = schema_config

    is_going: bool = Field(
        ...,
        description="Whether the current user is RSVP'd to the event",
    )
    attendee_count: int = Field(
        ...,
        description="The total count of attendees for the event",
        ge=0,
    )
