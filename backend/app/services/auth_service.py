"""Password hashing + JWT issuing/verification for per-user auth.

Uses `bcrypt` directly rather than `passlib[bcrypt]`: passlib's last
release (1.7.4, 2020) reads `bcrypt.__about__.__version__`, which bcrypt
dropped in 4.1+, so passlib+modern-bcrypt raises on import in a lot of
environments. One well-maintained library, one job — no wrapper needed.
"""
import datetime as dt
from typing import Optional

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed hash (shouldn't happen for rows we wrote ourselves) —
        # treat as "wrong password" rather than crashing the login attempt.
        return False


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    if not settings.JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not configured")

    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + dt.timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[int]:
    """Returns the user id encoded in a valid, unexpired token, or None."""
    settings = get_settings()
    if not settings.JWT_SECRET:
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        return int(sub)
    except (TypeError, ValueError):
        return None
