"""Auth for the REST API — two layers, doing two different jobs:

- `verify_api_key`: a single shared secret (X-API-Key), gating the API at
  the service level. Predates per-user accounts (Stage 1) and is kept
  as-is on top of JWT auth rather than removed — it's cheap insurance
  against the bare-HTTP-IP deployment (see PROJECT_AUDIT.md) being probed
  by anything that doesn't even know this is a multi-user app yet.
- `get_current_user`: per-user identity via a JWT in an httpOnly
  `access_token` cookie (not a header/localStorage — keeps the token out
  of reach of any XSS in the frontend bundle). This is what every
  user-data endpoint (leads, search profiles, ...) actually authorizes
  against.
"""
import hmac
from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.user import User
from app.services.auth_service import decode_access_token


async def verify_api_key(x_api_key: str = Header(default="")) -> None:
    settings = get_settings()

    if not settings.API_KEY:
        # main.py's startup check refuses to boot with API_KEY unset
        # outside of development, so reaching this in production would
        # mean that check was bypassed — fail closed rather than silently
        # let every request through.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured",
        )

    if not x_api_key or not hmac.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


async def get_current_user(
    access_token: Optional[str] = Cookie(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Cookie"},
    )
    if not access_token:
        raise unauthorized

    user_id = decode_access_token(access_token)
    if user_id is None:
        raise unauthorized

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized

    return user


async def get_current_user_optional(
    access_token: Optional[str] = Cookie(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    """Same lookup as get_current_user, but returns None instead of 401 —
    for endpoints reachable both logged-out (e.g. Telegram LOGIN) and
    logged-in (e.g. Telegram LINK) that decide which case they're in
    themselves. Never use this where an endpoint actually requires a
    session; that's what get_current_user is for."""
    if not access_token:
        return None
    user_id = decode_access_token(access_token)
    if user_id is None:
        return None
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


async def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
