import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator

from feynman_api.auth.passwords import PASSWORD_MAX, PASSWORD_MIN, normalize_password


def _clean_email(value: str) -> str:
    return value.strip().lower()


def _require_encodable(value: str) -> None:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        # Fixed message: never echo the value or the exception text.
        raise ValueError("Password contains invalid characters.") from None


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    created_at: datetime


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    birth_month: Annotated[int, Field(ge=1, le=12)]
    birth_year: int

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return _clean_email(value)

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        _require_encodable(value)
        normalised = normalize_password(value)
        if not PASSWORD_MIN <= len(normalised) <= PASSWORD_MAX:
            # Fixed message: never echo the value.
            raise ValueError(f"Password must be {PASSWORD_MIN} to {PASSWORD_MAX} characters.")
        return normalised


class LoginIn(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(max_length=1024)]

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return _clean_email(value)

    @field_validator("password")
    @classmethod
    def _password_encodable(cls, value: str) -> str:
        _require_encodable(value)
        return value


class DeleteAccountIn(BaseModel):
    password: Annotated[str, Field(max_length=1024)]

    @field_validator("password")
    @classmethod
    def _password_encodable(cls, value: str) -> str:
        _require_encodable(value)
        return value
