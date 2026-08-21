"""FastAPI application entrypoint (app factory)."""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.keywords import router as keywords_router
from app.api.leads import router as leads_router
from app.api.legal import admin_router as legal_admin_router
from app.api.legal import public_router as legal_public_router
from app.api.search_profile_keywords import router as search_profile_keywords_router
from app.api.search_profile_sources import router as search_profile_sources_router
from app.api.search_profiles import router as search_profiles_router
from app.api.sources import router as sources_router
from app.api.subscription import router as subscription_router
from app.api.telegram_auth import router as telegram_auth_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.security import get_current_admin_user, verify_api_key

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("%s starting up in '%s' environment", settings.APP_NAME, settings.ENV)
    yield
    logger.info("%s shutting down", settings.APP_NAME)


def create_app() -> FastAPI:
    settings = get_settings()

    # Fail loudly at boot rather than silently serving an unauthenticated
    # API — this backend is reachable on a public IP once deployed, and an
    # unset API_KEY there means anyone can read/modify/delete all data.
    if not settings.API_KEY and settings.ENV != "development":
        raise RuntimeError(
            "API_KEY must be set when ENV is not 'development' — refusing to start "
            "an internet-reachable API with no authentication."
        )
    if not settings.JWT_SECRET and settings.ENV != "development":
        raise RuntimeError(
            "JWT_SECRET must be set when ENV is not 'development' — refusing to start "
            "with unverifiable user sessions."
        )

    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="ReadHunter — automated lead discovery for web dev/design services.",
        lifespan=lifespan,
    )

    # CORS_ALLOWED_ORIGINS is a comma-separated list (see Settings) —
    # `["*"]` combined with allow_credentials was both overly permissive
    # (any site could call this API from a visitor's browser) and
    # technically invalid per the CORS spec (browsers refuse to honor
    # credentials with a wildcard origin), so it silently didn't even work
    # the way it looked like it did.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # This is a JSON API, not HTML — so browser-rendering headers like CSP
    # matter less here than on the frontend, but nosniff/no-store are cheap
    # and close off MIME-sniffing tricks and response caching of
    # potentially sensitive lead data by shared caches/proxies.
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(health_router)
    # Public, unauthenticated — the /privacy /terms /cookies pages and the
    # bot's /privacy command all read from this.
    app.include_router(legal_public_router)
    # No verify_api_key here — register/login must be reachable by anyone
    # with no credentials yet. Rate-limited instead (see app/api/auth.py).
    app.include_router(auth_router)
    # Telegram half of auth — /start, /status, /complete are reachable
    # logged-out (LOGIN) just like register/login above; /link/start
    # requires a session (see app/api/telegram_auth.py).
    app.include_router(telegram_auth_router)
    # Gated per-route by get_current_user (JWT cookie) — user-owned data,
    # scoped to whoever's logged in. Replaces the old blanket X-API-Key
    # gate now that there's a real per-user identity to check.
    app.include_router(search_profiles_router)
    app.include_router(leads_router)
    # analytics_router now resolves the caller's own SearchProfile and
    # scopes every query to it (see app/api/analytics.py) — same isolation
    # model as leads_router, so it's per-user JWT-gated, not admin-only.
    app.include_router(analytics_router)
    # Per-profile links to the shared Source/Keyword catalogs — JWT-only,
    # every route ownership-checks the SearchProfile itself (see
    # app/api/search_profile_sources.py / search_profile_keywords.py).
    # This is the multi-search-profile ТЗ's per-user layer on top of the
    # still-admin-curated global catalogs below.
    app.include_router(search_profile_sources_router)
    app.include_router(search_profile_keywords_router)
    # Read-only plan/usage panel (Этап 11) — same per-user JWT gate,
    # resolves the caller's own Subscription only.
    app.include_router(subscription_router)
    # The flat /api/sources, /api/keywords stay admin-only: they manage the
    # shared, system-wide catalog rows themselves (name/url/weight/etc for
    # everyone), as opposed to a profile's personal link to a catalog row
    # (which any signed-in user manages for their own profile above).
    # verify_api_key is kept in addition as defense in depth for the
    # bare-HTTP-IP deployment (see PROJECT_AUDIT.md) — TODO: drop once a
    # domain + TLS is in place and NEXT_PUBLIC_API_KEY's exposure in the
    # client bundle stops mattering.
    app.include_router(
        sources_router, dependencies=[Depends(verify_api_key), Depends(get_current_admin_user)]
    )
    app.include_router(
        keywords_router, dependencies=[Depends(verify_api_key), Depends(get_current_admin_user)]
    )
    # admin_router's own routes already depend on get_current_admin_user
    # per-route (see app/api/admin.py) — no router-level dependency needed.
    app.include_router(admin_router)
    app.include_router(legal_admin_router)

    return app


app = create_app()
