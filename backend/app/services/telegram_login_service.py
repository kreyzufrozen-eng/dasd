"""Bot-initiated "Войти через Telegram" handshake — no Telegram Login
Widget, no domain/HTTPS requirement (see IMPLEMENTATION_PLAN's Telegram
auth notes): the site issues a one-time token, the user confirms it by
opening a bot deep link, the site polls for confirmation and then
completes the login/link itself.

Three steps, three functions:
  start()    — site: mint a token, return it (plaintext, once) + the deep
               link payload. Only token_hash is ever persisted.
  confirm()  — bot's /start handler: the real Telegram user tapped the
               link: flip PENDING -> CONFIRMED and record their identity.
  complete() — site: once status is CONFIRMED, actually create/log-in the
               User (LOGIN) or attach telegram_id to the caller's own
               account (LINK), then consume the token (single-use).

Security properties required by IMPLEMENTATION_PLAN_TELEGRAM_LOGIN.md:
tokens are cryptographically random, short-TTL, single-use, stored only
as a SHA-256 hash, bound to a specific user for LINK, and the deep link
itself never carries a user_id/session/access token — just this opaque,
purpose-scoped, hashed-at-rest token.
"""
import datetime as dt
import hashlib
import secrets
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import TelegramTokenPurpose, TelegramTokenStatus
from app.models.telegram_login_token import TelegramLoginToken
from app.models.user import User
from app.repositories.telegram_login_token_repository import TelegramLoginTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.legal_acceptance_service import (
    legal_acceptance_required,
    record_signup_acceptance,
)
from app.services.subscription_service import ensure_free_subscription


class TelegramLoginError(Exception):
    """User-facing: message is safe to return as an API error detail."""


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_aware_utc(value: dt.datetime) -> dt.datetime:
    """SQLite (used in tests) round-trips DateTime(timezone=True) as
    naive; Postgres (prod/dev) doesn't. Every value this module writes is
    already UTC, so a naive read is always UTC too — same pattern as
    app/services/lead_scoring.py."""
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


def _parse_payload(payload: str) -> Optional[tuple[TelegramTokenPurpose, str]]:
    if "-" not in payload:
        return None
    prefix, token = payload.split("-", 1)
    if not token:
        return None
    try:
        return TelegramTokenPurpose(prefix), token
    except ValueError:
        return None


@dataclass(frozen=True)
class TelegramLoginStart:
    token: str
    deep_link_payload: str
    expires_at: dt.datetime


async def start(
    session: AsyncSession, purpose: TelegramTokenPurpose, user_id: Optional[int] = None
) -> TelegramLoginStart:
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
        seconds=settings.TELEGRAM_LOGIN_TOKEN_TTL_SECONDS
    )
    repo = TelegramLoginTokenRepository(session)
    await repo.create(
        token_hash=_hash_token(token),
        purpose=purpose.value,
        status=TelegramTokenStatus.PENDING.value,
        user_id=user_id,
        expires_at=expires_at,
    )
    await session.commit()
    return TelegramLoginStart(
        token=token, deep_link_payload=f"{purpose.value}-{token}", expires_at=expires_at
    )


async def confirm(
    session: AsyncSession,
    payload: str,
    telegram_id: int,
    telegram_username: Optional[str],
    telegram_first_name: Optional[str],
) -> bool:
    """Bot-side. Returns False for anything invalid rather than raising —
    the /start payload is public input from Telegram, not a trusted API
    caller, so there's no "error detail" worth surfacing back to the bot
    beyond a generic failure message."""
    parsed = _parse_payload(payload)
    if parsed is None:
        return False
    purpose, token = parsed

    repo = TelegramLoginTokenRepository(session)
    row = await repo.get_by_token_hash(_hash_token(token))
    now = dt.datetime.now(dt.timezone.utc)
    if row is None or row.purpose != purpose.value or row.status != TelegramTokenStatus.PENDING.value:
        return False
    if _as_aware_utc(row.expires_at) < now:
        await repo.update(row, status=TelegramTokenStatus.EXPIRED.value)
        await session.commit()
        return False

    await repo.update(
        row,
        status=TelegramTokenStatus.CONFIRMED.value,
        telegram_id=telegram_id,
        telegram_username=telegram_username,
        telegram_first_name=telegram_first_name,
        confirmed_at=now,
    )
    await session.commit()
    return True


async def get_status(session: AsyncSession, token: str) -> Optional[TelegramLoginToken]:
    repo = TelegramLoginTokenRepository(session)
    row = await repo.get_by_token_hash(_hash_token(token))
    if row is None:
        return None
    now = dt.datetime.now(dt.timezone.utc)
    if row.status == TelegramTokenStatus.PENDING.value and _as_aware_utc(row.expires_at) < now:
        await repo.update(row, status=TelegramTokenStatus.EXPIRED.value)
        await session.commit()
    return row


async def complete(
    session: AsyncSession,
    token: str,
    current_user_id: Optional[int],
    accept_legal: bool,
    ip_address: str,
    user_agent: str,
) -> User:
    """Raises TelegramLoginError with a user-facing message on any invalid
    state. Caller (the API route) still owns issuing/clearing the session
    cookie — this only returns the resulting User.

    accept_legal/ip_address/user_agent are only consulted when this call
    actually creates a brand-new account (LOGIN purpose, no existing user
    for that telegram_id) — an existing account being logged back in, or a
    LINK, already went through consent at its original signup."""
    repo = TelegramLoginTokenRepository(session)
    row = await repo.get_by_token_hash(_hash_token(token))
    now = dt.datetime.now(dt.timezone.utc)
    if row is None or row.status != TelegramTokenStatus.CONFIRMED.value:
        raise TelegramLoginError("Токен недействителен или ещё не подтверждён в Telegram")
    if _as_aware_utc(row.expires_at) < now:
        raise TelegramLoginError("Токен истёк, попробуйте снова")

    user_repo = UserRepository(session)

    if row.purpose == TelegramTokenPurpose.LINK.value:
        if row.user_id is None or current_user_id is None or row.user_id != current_user_id:
            raise TelegramLoginError("Токен не относится к вашей сессии")
        user = await user_repo.get(row.user_id)
        if user is None:
            raise TelegramLoginError("Аккаунт не найден")
        existing = await user_repo.get_by_telegram_id(row.telegram_id)  # type: ignore[arg-type]
        if existing is not None and existing.id != user.id:
            raise TelegramLoginError("Этот аккаунт Telegram уже привязан к другому пользователю")
        user = await user_repo.update(
            user, telegram_id=row.telegram_id, telegram_username=row.telegram_username
        )
    else:
        user = await user_repo.get_by_telegram_id(row.telegram_id)  # type: ignore[arg-type]
        if user is None:
            if not accept_legal and await legal_acceptance_required(session):
                raise TelegramLoginError(
                    "Нужно подтвердить согласие с политикой обработки данных и условиями использования"
                )
            user = await user_repo.create(
                telegram_id=row.telegram_id,
                telegram_username=row.telegram_username,
                name=row.telegram_first_name,
            )
            await ensure_free_subscription(session, user.id)
            await record_signup_acceptance(session, user.id, ip_address, user_agent)

    await repo.update(row, status=TelegramTokenStatus.CONSUMED.value, consumed_at=now)
    await session.commit()
    return user
