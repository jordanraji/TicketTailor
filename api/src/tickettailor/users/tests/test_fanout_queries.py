"""Service-level tests for the relay fan-out support queries (ADR-0016):
``ClubFollowService.followers_for_club`` and ``UserService.contact_details_for``.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.users.models import ClubFollow, PushSubscription, User
from tickettailor.users.service import ClubFollowService, UserService

pytestmark = pytest.mark.asyncio


async def _make_user(db: AsyncSession, *, display_name: str = "Test User") -> User:
    user = User(
        email=f"{uuid.uuid4()}@example.com",
        password_hash="x",
        display_name=display_name,
    )
    db.add(user)
    await db.flush()
    return user


async def test_followers_for_club_returns_only_that_clubs_followers(
    db_session: AsyncSession,
) -> None:
    club_a, club_b = uuid.uuid4(), uuid.uuid4()
    u1, u2, u3 = (
        await _make_user(db_session),
        await _make_user(db_session),
        await _make_user(db_session),
    )
    db_session.add_all(
        [
            ClubFollow(user_id=u1.id, club_id=club_a),
            ClubFollow(user_id=u2.id, club_id=club_a),
            ClubFollow(user_id=u3.id, club_id=club_b),
        ]
    )
    await db_session.flush()

    followers = await ClubFollowService().followers_for_club(db_session, club_a)
    assert set(followers) == {u1.id, u2.id}


async def test_followers_for_club_empty_when_none(db_session: AsyncSession) -> None:
    followers = await ClubFollowService().followers_for_club(db_session, uuid.uuid4())
    assert followers == []


async def test_contact_details_include_email_name_and_latest_push(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, display_name="Jane Doe")
    now = datetime.now(UTC)
    db_session.add_all(
        [
            PushSubscription(
                user_id=user.id,
                endpoint="https://push/old",
                p256dh="oldp",
                auth="olda",
                created_at=now - timedelta(hours=1),
            ),
            PushSubscription(
                user_id=user.id,
                endpoint="https://push/new",
                p256dh="newp",
                auth="newa",
                created_at=now,
            ),
        ]
    )
    await db_session.flush()

    contacts = await UserService().contact_details_for(db_session, [user.id])

    assert len(contacts) == 1
    contact = contacts[0]
    assert contact.user_id == user.id
    assert contact.email == user.email
    assert contact.display_name == "Jane Doe"
    assert contact.push_subscription is not None
    # Most recent subscription wins.
    assert contact.push_subscription.endpoint == "https://push/new"


async def test_contact_details_push_none_without_subscription(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    contacts = await UserService().contact_details_for(db_session, [user.id])
    assert len(contacts) == 1
    assert contacts[0].push_subscription is None


async def test_contact_details_skip_soft_deleted_users(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    user.deleted_at = datetime.now(UTC)
    await db_session.flush()

    assert await UserService().contact_details_for(db_session, [user.id]) == []


async def test_contact_details_empty_for_empty_input(
    db_session: AsyncSession,
) -> None:
    assert await UserService().contact_details_for(db_session, []) == []
