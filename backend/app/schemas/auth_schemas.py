import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)
    name: Optional[str] = Field(default=None, max_length=255)
    # Must be explicitly true, not defaulted from a pre-checked frontend
    # checkbox — see app/services/legal_acceptance_service.py.
    accept_legal: bool = False


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class ChangePassword(BaseModel):
    # None only when the account has no password yet (Telegram-only,
    # setting one for the first time) — see app/api/auth.py.
    current_password: Optional[str] = None
    new_password: str = Field(min_length=8, max_length=255)


class DeleteAccountRequest(BaseModel):
    # Required when the account has a password — re-verifies the session
    # is really the account owner, not just a valid cookie. Ignored for a
    # Telegram-only account (nothing to check it against).
    password: Optional[str] = None
    # Must be explicitly true — the frontend's "Danger Zone" confirmation,
    # never defaulted.
    confirm: bool = False


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Nullable: a Telegram-only account (see app/models/user.py) has no
    # email. The frontend uses has_password/has_telegram, not these
    # fields' presence, to decide what Settings offers.
    email: Optional[str] = None
    telegram_username: Optional[str] = None
    name: Optional[str] = None
    is_admin: bool
    created_at: dt.datetime
    has_password: bool
    has_telegram: bool

    @model_validator(mode="before")
    @classmethod
    def _derive_auth_flags(cls, data: Any) -> Any:
        """Every endpoint just `return`s the ORM User object — this
        computes has_password/has_telegram from its real columns before
        the rest of validation runs, so no call site needs to change."""
        if isinstance(data, dict):
            return data
        return {
            "id": data.id,
            "email": data.email,
            "telegram_username": data.telegram_username,
            "name": data.name,
            "is_admin": data.is_admin,
            "created_at": data.created_at,
            "has_password": data.password_hash is not None,
            "has_telegram": data.telegram_id is not None,
        }
