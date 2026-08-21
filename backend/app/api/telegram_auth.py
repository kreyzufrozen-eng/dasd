"""REST API: /api/auth/telegram — the site's half of the bot-initiated
"Войти через Telegram" handshake (see app/services/telegram_login_service.py
for the full flow and app/bot/public_handlers.py for the bot's half).

/start and /link/start are rate-limited per client IP like the rest of
app/api/auth.py; /status is polled frequently by design (the frontend
waits for CONFIRMED) so it gets a looser limit than the others.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import InvalidInputError, NotFoundError
from app.core.rate_limit import rate_limit
from app.core.security import get_current_user, get_current_user_optional
from app.db.session import get_db_session
from app.models.enums import TelegramTokenPurpose
from app.models.user import User
from app.schemas.auth_schemas import UserRead
from app.schemas.telegram_login_schemas import (
    TelegramLoginCompleteRequest,
    TelegramLoginStartResponse,
    TelegramLoginStatusResponse,
)
from app.services import telegram_login_service
from app.services.audit_log_service import log_action

router = APIRouter(prefix="/api/auth/telegram", tags=["auth"])

COOKIE_NAME = "access_token"


def _set_session_cookie(response: Response, user_id: int) -> None:
    from app.services.auth_service import create_access_token

    settings = get_settings()
    token = create_access_token(user_id)
    secure = settings.COOKIE_SECURE if settings.COOKIE_SECURE is not None else settings.ENV != "development"
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/",
    )


def _deep_link(payload: str) -> str:
    settings = get_settings()
    username = settings.TELEGRAM_BOT_USERNAME
    if not username:
        raise InvalidInputError(
            "Вход через Telegram ещё не настроен на сервере (TELEGRAM_BOT_USERNAME)"
        )
    return f"https://t.me/{username}?start={payload}"


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post(
    "/start",
    response_model=TelegramLoginStartResponse,
    dependencies=[Depends(rate_limit("telegram_login_start", max_attempts=10, window_seconds=300))],
)
async def start_login(
    request: Request, db: AsyncSession = Depends(get_db_session)
) -> TelegramLoginStartResponse:
    result = await telegram_login_service.start(db, TelegramTokenPurpose.LOGIN)
    return TelegramLoginStartResponse(
        token=result.token,
        deep_link=_deep_link(result.deep_link_payload),
        expires_at=result.expires_at,
    )


@router.post(
    "/link/start",
    response_model=TelegramLoginStartResponse,
    dependencies=[Depends(rate_limit("telegram_link_start", max_attempts=10, window_seconds=300))],
)
async def start_link(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> TelegramLoginStartResponse:
    result = await telegram_login_service.start(db, TelegramTokenPurpose.LINK, user_id=user.id)
    return TelegramLoginStartResponse(
        token=result.token,
        deep_link=_deep_link(result.deep_link_payload),
        expires_at=result.expires_at,
    )


@router.get(
    "/status",
    response_model=TelegramLoginStatusResponse,
    dependencies=[Depends(rate_limit("telegram_login_status", max_attempts=120, window_seconds=60))],
)
async def get_status(token: str, db: AsyncSession = Depends(get_db_session)) -> TelegramLoginStatusResponse:
    row = await telegram_login_service.get_status(db, token)
    if row is None:
        raise NotFoundError("Токен не найден")
    return TelegramLoginStatusResponse(status=row.status)


@router.post(
    "/complete",
    response_model=UserRead,
    dependencies=[Depends(rate_limit("telegram_login_complete", max_attempts=20, window_seconds=300))],
)
async def complete_login(
    payload: TelegramLoginCompleteRequest,
    request: Request,
    response: Response,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    try:
        user = await telegram_login_service.complete(
            db,
            payload.token,
            current_user_id=current_user.id if current_user else None,
            accept_legal=payload.accept_legal,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
        )
    except telegram_login_service.TelegramLoginError as exc:
        raise InvalidInputError(str(exc)) from exc

    await log_action(
        db,
        action="telegram_connect",
        user_id=user.id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    _set_session_cookie(response, user.id)
    return user
