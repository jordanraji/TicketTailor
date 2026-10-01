import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from tickettailor.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from tickettailor.auth.service import AuthService
from tickettailor.shared.app_services import get_db_session
from tickettailor.shared.logging import logger
from tickettailor.shared.security import require_current_user_id
from tickettailor.users.schemas import UserResponse
from tickettailor.users.service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
) -> RegisterResponse:
    logger.info(f"Registering user: {body.email}")
    user = await AuthService().register(
        db, body.email, body.password, body.display_name
    )
    # Commit before responding so the new account is immediately usable. FastAPI
    # (>=0.106) runs the get_db_session commit in post-response teardown, so a
    # client that logs in right after the 201 would otherwise race the
    # registration commit - and, on the read replica, its lag (ADR-0008). The
    # sessionmaker uses expire_on_commit=False, so `user` stays usable here.
    await db.commit()
    return RegisterResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    logger.info(f"Login attempt: {body.email}")
    access_token, refresh_token = await AuthService().login(
        db, body.email, body.password
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    access_token, refresh_token = await AuthService().rotate_refresh(
        db, body.refresh_token
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await AuthService().logout(db, body.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(
    user_id: uuid.UUID = Depends(require_current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    user = await UserService().get_user_by_id(db, user_id)
    return UserResponse.model_validate(user)
