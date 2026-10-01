class TicketTailorError(Exception):
    def __init__(self, status_code: int, title: str, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.title = title
        self.detail = detail


class InvalidCredentialsError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            title="Invalid Credentials",
            detail="The email or password is incorrect.",
        )


class InvalidTokenError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            title="Invalid Token",
            detail="The authentication token is missing, expired, or invalid.",
        )


class UserAlreadyExistsError(TicketTailorError):
    def __init__(self, email: str):
        super().__init__(
            status_code=400,
            title="User Already Exists",
            detail=f"A user with email '{email}' is already registered.",
        )


class UserNotFoundError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="User Not Found",
            detail="The requested user was not found.",
        )


class AlreadyFollowingError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            title="Already Following",
            detail="The user is already following this club.",
        )


class FollowNotFoundError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Follow Relationship Not Found",
            detail="The follow relationship does not exist.",
        )


class SubscriptionNotFoundError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Push Subscription Not Found",
            detail="The push subscription does not exist.",
        )


class ClubAlreadyExistsError(TicketTailorError):
    def __init__(self, name: str) -> None:
        super().__init__(
            status_code=400,
            title="Club Already Exists",
            detail=f"A club named '{name}' already exists.",
        )


class ClubNotFoundError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Club Not Found",
            detail="The requested club was not found.",
        )


class NotClubAdminError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            title="Forbidden",
            detail="You must be a club admin to perform this action.",
        )


class AlreadyClubMemberError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            title="Already Club Member",
            detail="The user is already a member of this club.",
        )


class MembershipNotFoundError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Membership Not Found",
            detail="The requested club membership was not found.",
        )


class EventNotFoundError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Event Not Found",
            detail="The requested event was not found.",
        )


class InvalidCursorError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            title="Invalid Cursor",
            detail="The pagination cursor is invalid.",
        )


class IncompleteGeoFilterError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            title="Incomplete Geo Filter",
            detail=(
                "lat, lng, and radius_m must all be provided together for a map search."
            ),
        )


class NotClubOrganiserError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            title="Forbidden",
            detail=(
                "You must be a club admin or committee member to perform this action."
            ),
        )


class AlreadyRsvpedError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Already RSVP'd",
            detail="The user is already RSVP'd to this event.",
        )


class RsvpNotFoundError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="RSVP Not Found",
            detail="The RSVP record does not exist.",
        )


class NotClubMemberError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            title="Forbidden",
            detail="You must be a club member to perform this action.",
        )


class CalendarTokenNotFoundError(TicketTailorError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Calendar Token Not Found",
            detail="The requested calendar feed token is invalid or has been revoked.",
        )
