"""REST API: /api/auth — registration, login/logout, password change.

Session token is a JWT in an httpOnly, SameSite=Strict cookie (not a
header the frontend has to remember to attach, not localStorage where an
XSS could read it). Login/register are rate-limited per client IP — see
app/core/rate_limit.py.
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, InvalidInputError
from app.core.rate_limit import rate_limit
from app.core.security import get_current_user, get_current_user_optional
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schemas import (
    ChangePassword,
    DeleteAccountRequest,
    UserLogin,
    UserRead,
    UserRegister,
)
from app.services.audit_log_service import log_action
from app.services.auth_service import create_access_token, hash_password, verify_password
from app.services.data_export_service import build_user_export
from app.services.legal_acceptance_service import (
    legal_acceptance_required,
    record_signup_acceptance,
)
from app.services.subscription_service import ensure_free_subscription

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "access_token"


def _set_session_cookie(response: Response, user_id: int) -> None:
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


@router.post(
    "/register",
    response_model=UserRead,
    status_code=201,
    dependencies=[Depends(rate_limit("register", max_attempts=5, window_seconds=300))],
)
async def register(
    payload: UserRegister,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    if not payload.accept_legal and await legal_acceptance_required(db):
        raise InvalidInputError(
            "Нужно подтвердить согласие с политикой обработки данных и условиями использования"
        )

    user_repo = UserRepository(db)
    email = payload.email.lower()

    existing = await user_repo.get_by_email(email)
    if existing is not None:
        raise ConflictError("An account with this email already exists")

    user = await user_repo.create(
        email=email, password_hash=hash_password(payload.password), name=payload.name
    )
    await ensure_free_subscription(db, user.id)
    await record_signup_acceptance(
        db,
        user.id,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", ""),
    )
    await log_action(db, action="register", user_id=user.id, target_type="user", target_id=user.id)
    await db.commit()

    _set_session_cookie(response, user.id)
    return user


@router.post(
    "/login",
    response_model=UserRead,
    dependencies=[Depends(rate_limit("login", max_attempts=10, window_seconds=300))],
)
async def login(
    payload: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(payload.email.lower())

    # Same error for "no such user", "wrong password", and "this account
    # has no password" (Telegram-only) — distinguishing any of these tells
    # an attacker which emails are registered / how an account authenticates.
    if (
        user is None
        or not user.is_active
        or user.password_hash is None
        or not verify_password(payload.password, user.password_hash)
    ):
        raise InvalidInputError("Incorrect email or password")

    await log_action(db, action="login", user_id=user.id, target_type="user", target_id=user.id)
    await db.commit()

    _set_session_cookie(response, user.id)
    return user


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    # Stays reachable with no/expired/invalid session — clearing a cookie
    # that may already be gone is idempotent by design, not an error.
    if user is not None:
        await log_action(db, action="logout", user_id=user.id, target_type="user", target_id=user.id)
        await db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/change-password", status_code=204)
async def change_password(
    payload: ChangePassword,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    # A Telegram-only account (no password_hash yet) is *setting* its
    # first password, not changing one — nothing to verify against.
    if user.password_hash is not None:
        if payload.current_password is None or not verify_password(
            payload.current_password, user.password_hash
        ):
            raise InvalidInputError("Current password is incorrect")

    user_repo = UserRepository(db)
    await user_repo.update(user, password_hash=hash_password(payload.new_password))
    await db.commit()


@router.get(
    "/export-data",
    dependencies=[Depends(rate_limit("export_data", max_attempts=5, window_seconds=3600))],
)
async def export_data(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)
) -> Response:
    data = await build_user_export(db, user)
    await log_action(db, action="data_export", user_id=user.id, target_type="user", target_id=user.id)
    await db.commit()

    body = json.dumps(data, default=str, ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="readhunter-export-{user.id}.json"'},
    )


@router.post(
    "/delete-account",
    status_code=204,
    dependencies=[Depends(rate_limit("delete_account", max_attempts=5, window_seconds=3600))],
)
async def delete_account(
    payload: DeleteAccountRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    if not payload.confirm:
        raise InvalidInputError("Нужно подтвердить удаление аккаунта")

    if user.password_hash is not None:
        if not payload.password or not verify_password(payload.password, user.password_hash):
            raise InvalidInputError("Неверный пароль")

    await log_action(
        db, action="account_deletion", user_id=user.id, target_type="user", target_id=user.id
    )

    user_repo = UserRepository(db)
    await user_repo.delete(user)
    await db.commit()

    response.delete_cookie(COOKIE_NAME, path="/")
