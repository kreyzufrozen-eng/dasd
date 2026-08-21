"""Application configuration loaded from environment variables (.env)."""
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    All secrets/config MUST come from environment variables (.env in dev).
    Never hardcode secrets here.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "ReadHunter"
    ENV: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # --- API auth ---
    # Shared-secret key required on every /api/* request (header: X-API-Key).
    # None disables auth — only ever acceptable for local dev; main.py
    # refuses to start with auth disabled unless ENV=development.
    # Kept alongside per-user JWT auth (below) as a service-level fallback
    # for the worker/bot's own DB access, which bypasses the API entirely
    # and never sends this header — X-API-Key currently only gates the
    # frontend-facing routers, same as before Stage 1.
    API_KEY: Optional[str] = None

    # --- Per-user auth (Stage 1) ---
    # Signs/verifies the JWT stored in the httpOnly `access_token` cookie.
    # Same fail-closed rule as API_KEY: required outside development.
    JWT_SECRET: Optional[str] = None
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRE_MINUTES: int = Field(default=60 * 24 * 7)  # 7 days
    # Controls the session cookie's `Secure` attribute. None (default) =
    # auto: Secure on everywhere except ENV=development, so local `http://
    # localhost` still works. A browser silently DROPS a Secure cookie
    # received over plain HTTP — set this to `false` explicitly (never by
    # relying on ENV) for a deployment that's genuinely HTTP-only (no
    # domain/TLS yet, see PROJECT_AUDIT.md), or every login there will
    # appear to succeed and then immediately 401 on the next request. Flip
    # back to unset/true the moment TLS is in front of the API.
    COOKIE_SECURE: Optional[bool] = None

    # Comma-separated list of origins allowed to call the API from a
    # browser (e.g. "https://leads.example.com"). Defaults to localhost
    # dev ports only — deliberately NOT "*", see main.py.
    CORS_ALLOWED_ORIGINS: str = Field(default="http://localhost:3000")

    # --- Database ---
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://leadhunter:leadhunter@localhost:5432/leadhunter"
    )

    # --- Telegram monitoring (Telethon) ---
    TELEGRAM_API_ID: Optional[int] = None
    TELEGRAM_API_HASH: Optional[str] = None
    TELEGRAM_SESSION: Optional[str] = None
    TELEGRAM_ALLOWED_SOURCES: str = Field(
        default="",
        description="Comma-separated list of allowed public Telegram source usernames/links.",
    )

    # --- Telegram notification bot (aiogram) ---
    BOT_TOKEN: Optional[str] = None
    NOTIFICATION_CHAT_ID: Optional[str] = None
    # No leading @ — used to build https://t.me/<username>?start=... deep
    # links for the "Войти через Telegram" flow (app/bot/public_handlers.py).
    TELEGRAM_BOT_USERNAME: Optional[str] = None

    # --- Public site (used in bot messages: /privacy link, etc.) ---
    # Bare IP for now — see PROJECT_AUDIT.md, no domain/TLS yet. Update
    # once a real domain exists; nothing else in the login flow depends on
    # this being HTTPS (the Telegram Login *Widget* would, but the
    # bot-deep-link flow this app uses does not).
    PUBLIC_SITE_URL: str = Field(default="http://localhost:3000")

    # --- AI provider ---
    AI_PROVIDER: str = Field(default="mock", description="mock | openai_compatible")
    AI_BASE_URL: Optional[str] = None
    AI_API_KEY: Optional[str] = None
    AI_MODEL: str = Field(default="gpt-4o-mini")
    AI_REQUEST_TIMEOUT_SECONDS: float = Field(default=30.0)
    AI_MAX_RETRIES: int = Field(default=2)

    # --- Lead scoring / notifications ---
    NOTIFICATION_THRESHOLD: int = Field(default=60)
    VERY_HOT_THRESHOLD: int = Field(default=90)
    MIN_STORE_THRESHOLD: int = Field(default=40)
    # Separate threshold for "hidden demand" leads (intent_score) — these
    # aren't asking for a site today, so a slightly higher bar than
    # NOTIFICATION_THRESHOLD avoids flooding notifications with weak
    # signals while still surfacing real ones.
    INTENT_NOTIFICATION_THRESHOLD: int = Field(default=70)

    # --- Scheduler ---
    TELEGRAM_POLL_INTERVAL_SECONDS: int = Field(default=60)

    # --- Data retention (see DATA_RETENTION_POLICY.md) ---
    # 90 days: long enough to cover analytics/funnel review over a normal
    # sales-cycle timeframe, short enough that raw third-party message text
    # doesn't accumulate indefinitely. An explicit owner decision to
    # tune, not a legally-mandated number — flagged as such in the policy
    # doc rather than treated as settled.
    RAW_ITEM_RETENTION_DAYS: int = Field(default=90)

    # --- Telegram login (see app/models/telegram_login_token.py) ---
    TELEGRAM_LOGIN_TOKEN_TTL_SECONDS: int = Field(default=600)  # 10 minutes

    @field_validator("TELEGRAM_API_ID", mode="before")
    @classmethod
    def _empty_string_to_none(cls, value: object) -> object:
        """.env leaves TELEGRAM_API_ID blank when Telegram isn't configured
        yet — env vars always arrive as strings, and an empty string isn't
        automatically treated as "unset" for an Optional[int] field, so
        without this it fails int-parsing instead of falling back to None."""
        if value == "":
            return None
        return value

    @property
    def allowed_source_list(self) -> list[str]:
        return [s.strip() for s in self.TELEGRAM_ALLOWED_SOURCES.split(",") if s.strip()]

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (singleton for process lifetime)."""
    return Settings()
