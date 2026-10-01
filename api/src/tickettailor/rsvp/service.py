import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.events.service import EventService, EventVisibility
from tickettailor.organisers.service import ClubMembershipService
from tickettailor.rsvp.repositories import RsvpRepository
from tickettailor.shared.app_services import app_services
from tickettailor.shared.exceptions import (
    AlreadyRsvpedError,
    NotClubMemberError,
    RsvpNotFoundError,
)
from tickettailor.shared.models import OutboxEvent, OutboxEventType
from tickettailor.shared.redis import RsvpCounter


@dataclass(frozen=True)
class ReconciliationResult:
    """Outcome of reconciling one event's live counter against the DB rows.

    ``redis_before`` is the counter value seen before correction (``None`` if
    the key was absent or Redis was unreachable); ``db_count`` is the
    authoritative row count; ``corrected`` is True when the two disagreed and
    the counter was overwritten to ``db_count``.
    """

    event_id: uuid.UUID
    db_count: int
    redis_before: int | None
    corrected: bool


class RsvpService:
    def __init__(self) -> None:
        self.rsvp_repo = RsvpRepository()
        self.event_service = EventService()
        self.membership_service = ClubMembershipService()
        self.counter = RsvpCounter(app_services.get_redis().client)

    async def _live_count(self, db: AsyncSession, event_id: uuid.UUID) -> int:
        """Read the live attendee count via Redis, seeding from the DB on miss.

        PostgreSQL is the system of record (ADR-0005): on a cache miss we seed
        the counter from a `COUNT(*)`, and if Redis is unreachable we fall back
        to the DB count so the request still succeeds (degraded, still correct).
        """
        cached = await self.counter.get(event_id)
        if cached is not None:
            return cached

        db_count = await self.rsvp_repo.get_count_by_event(db, event_id)
        await self.counter.seed(event_id, db_count)
        return db_count

    async def place_rsvp(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> int:
        """Place an RSVP for the given user on the specified event.

        Performs existence checks, visibility/membership authorization, and inserts
        an RSVP row along with a transactional Outbox event.
        """
        # NOTE: ADR-0005 also describes a Redis SET NX idempotency gate. It is
        # deliberately NOT implemented here yet - the gate as specified is not
        # cleared on cancel (so re-RSVP within the TTL would be silently
        # dropped) and would return the current count instead of the 409 these
        # endpoints contract on. The DB unique constraint + existence check
        # below are the hard correctness guarantee. Gate deferred pending an
        # ADR-0005 refinement; see the team note.
        #
        # The existence check at step 3 resolves duplicates that arrive in
        # series. Two *concurrent* RSVPs for the same (user, event) can both
        # pass that check before either commits; the unique constraint then
        # fails one insert. We translate that race into the same
        # AlreadyRsvpedError (409) the serial path returns, so a retried toggle
        # is idempotent-safe rather than surfacing a 500 (ADR-0005/0008
        # idempotency-under-retry). The counter increment runs only after a
        # successful insert, so the losing request never double-counts.

        # 1. Verify event exists (raises EventNotFoundError if missing)
        event = await self.event_service.get_event_by_id(db, event_id)

        # 2. Check visibility and club membership authorization
        if event.visibility == EventVisibility.club_only:
            is_member = await self.membership_service.is_member_of(
                db,
                user_id=user_id,
                club_id=event.club_id,
            )
            if not is_member:
                raise NotClubMemberError()

        # 3. Check for existing RSVP (idempotency check)
        existing = await self.rsvp_repo.get_by_user_and_event(db, user_id, event_id)
        if existing:
            raise AlreadyRsvpedError()

        # 4. Seed the counter from the pre-insert DB count on a cold key, so the
        #    write-through increment below lands on the correct base (ADR-0005).
        #    This must run BEFORE the insert, or the seed would already include
        #    the new row and the increment would double-count.
        await self._live_count(db, event_id)

        # 5. Insert RSVP record. A concurrent duplicate loses the unique
        #    constraint here (before any counter increment); treat it as a
        #    duplicate RSVP so retries stay idempotent (see note above).
        try:
            rsvp = await self.rsvp_repo.create(db, user_id, event_id)
        except IntegrityError as exc:
            raise AlreadyRsvpedError() from exc

        # 6. Insert event into transaction outbox
        outbox_event = OutboxEvent(
            aggregate_id=rsvp.id,
            event_type=OutboxEventType.rsvp_placed,
            payload={
                "rsvp_id": str(rsvp.id),
                "user_id": str(user_id),
                "event_id": str(event_id),
            },
        )
        db.add(outbox_event)

        # 7. Durably commit the RSVP row and its outbox event BEFORE touching
        #    the live counter. The counter is a cache over the committed rows
        #    (ADR-0005); incrementing it before the commit would leave a
        #    phantom count if the commit then failed (e.g. an RDS failover
        #    mid-write - the QA3 case). Committing here makes the ordering
        #    insert -> commit -> increment, so a failed commit raises before any
        #    Redis write. The request-scoped dependency's later commit is then a
        #    harmless no-op.
        await db.commit()

        # 8. Write-through the atomic counter; if Redis is unreachable, fall
        #    back to the authoritative DB count (degraded but correct).
        new_count = await self.counter.increment(event_id)
        if new_count is not None:
            return new_count
        return await self.rsvp_repo.get_count_by_event(db, event_id)

    async def cancel_rsvp(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> int:
        """Cancel an RSVP for the given user on the specified event.

        Performs existence checks, removes the RSVP row, and inserts a transactional
        Outbox event.
        """
        # 1. Verify event exists (raises EventNotFoundError if missing)
        await self.event_service.get_event_by_id(db, event_id)

        # 2. Check for existing RSVP
        rsvp = await self.rsvp_repo.get_by_user_and_event(db, user_id, event_id)
        if not rsvp:
            raise RsvpNotFoundError()

        # 3. Seed the counter from the pre-delete DB count on a cold key, so the
        #    write-through decrement below lands on the correct base (ADR-0005).
        #    Must run BEFORE the delete, or the seed would already exclude the
        #    removed row and the decrement would under-count.
        await self._live_count(db, event_id)

        # 4. Delete RSVP record
        await self.rsvp_repo.delete(db, user_id, event_id)

        # 5. Insert event into transaction outbox
        outbox_event = OutboxEvent(
            aggregate_id=rsvp.id,
            event_type=OutboxEventType.rsvp_cancelled,
            payload={
                "rsvp_id": str(rsvp.id),
                "user_id": str(user_id),
                "event_id": str(event_id),
            },
        )
        db.add(outbox_event)

        # 6. Durably commit the delete and its outbox event BEFORE touching the
        #    live counter, mirroring place_rsvp: the counter must only reflect
        #    committed rows, so a failed commit raises before any Redis write
        #    rather than leaving the counter decremented for a row that still
        #    exists. The dependency's later commit is then a harmless no-op.
        await db.commit()

        # 7. Write-through the atomic counter; if Redis is unreachable, fall
        #    back to the authoritative DB count (degraded but correct).
        new_count = await self.counter.decrement(event_id)
        if new_count is not None:
            return new_count
        return await self.rsvp_repo.get_count_by_event(db, event_id)

    async def get_rsvp_status(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        event_id: uuid.UUID,
    ) -> tuple[bool, int]:
        """Get the RSVP status and total attendee count for an event."""
        # 1. Verify event exists
        event = await self.event_service.get_event_by_id(db, event_id)

        # 2. Check visibility and club membership authorization
        if event.visibility == EventVisibility.club_only:
            is_member = await self.membership_service.is_member_of(
                db,
                user_id=user_id,
                club_id=event.club_id,
            )
            if not is_member:
                raise NotClubMemberError()

        # 3. Check RSVP status
        rsvp = await self.rsvp_repo.get_by_user_and_event(db, user_id, event_id)
        is_going = rsvp is not None

        # Read the live counter (ADR-0005), seeding from the DB on a cache miss.
        count = await self._live_count(db, event_id)

        return is_going, count

    async def get_events_rsvped_by_user(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        """Get all event IDs that the user has RSVP'd to."""
        return await self.rsvp_repo.get_events_rsvped_by_user(db, user_id)

    async def attendees_for_event(
        self,
        db: AsyncSession,
        event_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        """Return the user IDs who have RSVP'd to an event.

        Recipient set for the FR7 ``event_updated`` notification fan-out
        (ADR-0016)."""
        return await self.rsvp_repo.get_attendees_by_event(db, event_id)

    async def reconcile_event(
        self,
        db: AsyncSession,
        event_id: uuid.UUID,
    ) -> ReconciliationResult:
        """Correct the live counter for one event from the persisted rows.

        The reliability backstop named in ADR-0005 and ADR-0008: PostgreSQL is
        the system of record, so we recompute ``COUNT(*)`` for the event and,
        if the Redis counter disagrees (drift from a lost increment, an
        eviction, or a Redis restart mid-window), overwrite it with the truth.
        Returns a :class:`ReconciliationResult` describing what was found and
        whether a correction was applied - the caller logs/aggregates these.
        """
        db_count = await self.rsvp_repo.get_count_by_event(db, event_id)
        redis_before = await self.counter.get(event_id)
        if redis_before == db_count:
            return ReconciliationResult(
                event_id=event_id,
                db_count=db_count,
                redis_before=redis_before,
                corrected=False,
            )
        await self.counter.overwrite(event_id, db_count)
        return ReconciliationResult(
            event_id=event_id,
            db_count=db_count,
            redis_before=redis_before,
            corrected=True,
        )

    async def reconcile_all(
        self,
        db: AsyncSession,
    ) -> list[ReconciliationResult]:
        """Reconcile every event that currently has a live counter key.

        Enumerates the ``rsvp:count:*`` keys (so it touches only events with an
        active counter, not the whole events table) and reconciles each. This
        is the body of the nightly / on-demand reconciliation job (ADR-0008).
        """
        results: list[ReconciliationResult] = []
        async for event_id in self.counter.scan_event_ids():
            results.append(await self.reconcile_event(db, event_id))
        return results
