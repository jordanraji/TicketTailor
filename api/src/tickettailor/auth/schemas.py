import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from tickettailor.shared.validation import StrictTextModel


class RegisterRequest(StrictTextModel):
    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(
        ..., min_length=8, description="Plain password, at least 8 characters"
    )
    display_name: str = Field(..., min_length=1, max_length=100)


class RegisterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    created_at: datetime


class LoginRequest(StrictTextModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class RefreshRequest(StrictTextModel):
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
