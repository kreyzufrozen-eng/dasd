"""User: an authenticated account. Owns one or more SearchProfiles.

Two independent ways to authenticate — email+password (original) and
Telegram (bot-initiated login, see app/models/telegram_login_token.py) —
so both email/password_hash AND telegram_id/telegram_username are
nullable: a Telegram-only account has no password, an email-only account
has no Telegram link (until it's added later from Settings). Exactly one
of {password_hash set, telegram_id set} is enforced at the application
layer, not the DB, since "at least one identity" is a business rule, not
a structural one.
"""
from typing import Optional

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UpdatedAtMixin


class User(Base, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Telegram user ids exceed 32-bit range (BigInteger, not Integer).
    # Username is deliberately NOT used as an identifier anywhere — it can
    # change; telegram_id is the only thing ever looked up by.
    telegram_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Full name is optional at registration — collected (or refined) during
    # onboarding, not required to create the account.
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    search_profiles: Mapped[list["SearchProfile"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r}>"
