"""TelegramLoginToken: the one-time handshake between the website and the
bot for "Войти через Telegram" (see IMPLEMENTATION_PLAN_TELEGRAM_LOGIN.md).

Flow: site calls POST /api/auth/telegram/start -> row created with
status=PENDING and a random token; only token_hash (sha256) is ever
persisted, never the plaintext token, so a DB read can't be used to
impersonate a pending login. The plaintext token is embedded in a bot
deep link (t.me/<bot>?start=<token>) shown to the user — never the
session/access token itself, per the "don't put user_id/session token in
the deep link" requirement. The bot's /start handler flips it to
CONFIRMED once the real Telegram user taps the link. The site, which has
been polling GET /api/auth/telegram/status, then calls
POST /api/auth/telegram/complete to actually create the session — that
final step both consumes the token (single-use) and is a second place a
race can be rejected as more info fails to reflect anywhere else.
"""
import datetime as dt
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import TelegramTokenPurpose, TelegramTokenStatus
from app.models.mixins import TimestampMixin


class TelegramLoginToken(Base, TimestampMixin):
    __tablename__ = "telegram_login_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TelegramTokenStatus.PENDING.value
    )

    # Set only for purpose=LINK — the already-authenticated user this token
    # will attach a telegram_id to on confirm. NULL for purpose=LOGIN,
    # where confirm itself decides "existing user" vs "new user".
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )

    # Filled in by the bot's /start handler once the real Telegram user
    # confirms — NULL until then.
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TelegramLoginToken id={self.id} purpose={self.purpose} status={self.status}>"
