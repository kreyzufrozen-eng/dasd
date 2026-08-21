"""Telethon client construction from environment configuration."""
from telethon import TelegramClient

from app.core.config import Settings


def create_telegram_client(settings: Settings) -> TelegramClient:
    """Builds (but does not connect) a TelegramClient from env vars.

    Raises ValueError early if credentials are missing, so callers can
    decide to skip Telegram monitoring entirely rather than crash — the
    rest of the app must keep working without Telegram configured.
    """
    if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
        raise ValueError(
            "TELEGRAM_API_ID and TELEGRAM_API_HASH must be set to use Telegram monitoring"
        )

    session_name = settings.TELEGRAM_SESSION or "leadhunter_session"
    return TelegramClient(
        session_name,
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH,
        proxy=settings.telethon_proxy,
    )


def is_source_allowed(external_identifier: str, settings: Settings) -> bool:
    """Defense-in-depth allowlist check: even if a Source row exists in the
    DB, only actually poll it if it's in TELEGRAM_ALLOWED_SOURCES. Prevents
    monitoring a channel that was added to the DB but never explicitly
    permitted in the environment config.

    Case-insensitive: Telegram usernames themselves are case-insensitive
    (t.me/SomeChan and t.me/somechan are the same channel), so comparing
    case-sensitively here would silently reject a channel over nothing but
    a typing difference between the DB entry and the .env list."""
    allowed = settings.allowed_source_list
    if not allowed:
        return False
    normalized_allowed = {a.lstrip("@").lower() for a in allowed}
    return external_identifier.lstrip("@").lower() in normalized_allowed
