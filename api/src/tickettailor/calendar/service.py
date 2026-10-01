import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from icalendar import Calendar
from icalendar import Event as ICalEvent
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.calendar.repositories import CalendarTokenRepository
from tickettailor.events.service import EventService, EventVisibility
from tickettailor.organisers.service import ClubMembershipService
from tickettailor.rsvp.service import RsvpService
from tickettailor.shared.exceptions import (
    CalendarTokenNotFoundError,
    NotClubMemberError,
)


def generate_ical_content(events: list[Any]) -> str:
    """Generate RFC 5545 compliant iCal content using the icalendar library."""
    cal = Calendar()  # type: ignore[no-untyped-call]
    cal.add("prodid", "-//TicketTailor//Calendar Feed//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")

    now = datetime.now(UTC)

    for event in events:
        ical_event = ICalEvent()  # type: ignore[no-untyped-call]
        ical_event.add("uid", f"event-{event.id}@tickettailor.com")
        ical_event.add("dtstamp", now)
        ical_event.add("dtstart", event.starts_at)
        ical_event.add("dtend", event.starts_at + timedelta(hours=1))
        ical_event.add("summary", event.title)
        ical_event.add("location", f"{event.latitude},{event.longitude}")
        ical_event.add("geo", (float(event.latitude), float(event.longitude)))
        ical_event.add("description", f"TicketTailor Event: {event.title}")
        cal.add_component(ical_event)

    return cast(str, cal.to_ical().decode("utf-8"))


class CalendarService:
    def __init__(self) -> None:
        self.token_repo = CalendarTokenRepository()
        self.event_service = EventService()
        self.membership_service = ClubMembershipService()
        self.rsvp_service = RsvpService()

    async def get_or_create_token(self, db: AsyncSession, user_id: uuid.UUID) -> str:
        """Get the active token for a user, or generate a new one if none exists."""
        token_obj = await self.token_repo.get_by_user_id(db, user_id)
        if token_obj:
            return token_obj.token

        token_value = secrets.token_urlsafe(32)
        token_obj = await self.token_repo.create(db, user_id, token_value)
        return token_obj.token

    async def rotate_token(self, db: AsyncSession, user_id: uuid.UUID) -> str:
        """Revoke user's current tokens and generate a new token."""
        await self.token_repo.revoke_by_user_id(db, user_id)
        token_value = secrets.token_urlsafe(32)
        token_obj = await self.token_repo.create(db, user_id, token_value)
        return token_obj.token

    async def get_event_ical(
        self, db: AsyncSession, user_id: uuid.UUID, event_id: uuid.UUID
    ) -> str:
        """Generate iCal data for a single event, verifying visibility/membership
        authorization.

        Should be executed using the read replica database session.
        """
        event = await self.event_service.get_event_by_id(db, event_id)

        if event.visibility == EventVisibility.club_only:
            is_member = await self.membership_service.is_member_of(
                db, user_id=user_id, club_id=event.club_id
            )
            if not is_member:
                raise NotClubMemberError()

        return generate_ical_content([event])

    async def get_user_feed_ical(self, db: AsyncSession, token: str) -> str:
        """Generate a combined iCal feed for all events a user has RSVP'd to.

        Verifies the feed token validity, checks visibility permissions for each event,
        and skips restricted club-only events if the user is no longer a club member.
        Should be executed using the read replica database session.
        """
        token_obj = await self.token_repo.get_by_token(db, token)
        if not token_obj:
            raise CalendarTokenNotFoundError()

        user_id = token_obj.user_id
        event_ids = await self.rsvp_service.get_events_rsvped_by_user(db, user_id)
        if not event_ids:
            return generate_ical_content([])

        events_list = await self.event_service.get_events_by_ids(db, event_ids)

        events = []
        for event in events_list:
            if event.visibility == EventVisibility.club_only:
                is_member = await self.membership_service.is_member_of(
                    db, user_id=user_id, club_id=event.club_id
                )
                if not is_member:
                    continue

            events.append(event)

        return generate_ical_content(events)
