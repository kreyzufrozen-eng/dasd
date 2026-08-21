import datetime as dt

from pydantic import BaseModel


class TelegramLoginStartResponse(BaseModel):
    token: str
    deep_link: str
    expires_at: dt.datetime


class TelegramLoginStatusResponse(BaseModel):
    status: str


class TelegramLoginCompleteRequest(BaseModel):
    token: str
    # Only consulted if this call ends up creating a brand-new account —
    # see telegram_login_service.complete(). Must be explicitly true, not
    # defaulted from a pre-checked frontend checkbox.
    accept_legal: bool = False
