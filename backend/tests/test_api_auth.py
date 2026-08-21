"""Stage 1: /api/auth — register/login/logout/me/change-password against
the real JWT-in-cookie flow (no auth override, unlike api_client — this is
what exercises get_current_user/create_access_token/decode_access_token
for real)."""
import os
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.rate_limit import _attempts
from app.db.base import Base


@pytest_asyncio.fixture
async def auth_client() -> AsyncIterator[AsyncClient]:
    from app.db.session import get_db_session
    from app.main import app

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    _attempts.clear()  # rate limiter is a module-level dict shared across tests

    # create_access_token() requires JWT_SECRET regardless of ENV — set it
    # for the duration of this test and clear the lru_cache'd Settings so
    # the new value is actually read.
    previous_secret = os.environ.get("JWT_SECRET")
    os.environ["JWT_SECRET"] = "test-secret-do-not-use-in-prod"
    get_settings.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.pop(get_db_session, None)
    await engine.dispose()

    if previous_secret is None:
        os.environ.pop("JWT_SECRET", None)
    else:
        os.environ["JWT_SECRET"] = previous_secret
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "env,cookie_secure_override,expect_secure",
    [
        # Auto mode (COOKIE_SECURE unset): dev stays insecure, prod is secure.
        ("development", None, False),
        ("production", None, True),
        # Explicit override always wins — this is the actual production bug
        # this guards: a plain-HTTP deployment (ENV=production, no domain/
        # TLS yet) needs COOKIE_SECURE=false or the browser silently drops
        # the Set-Cookie response and every login 401s on the next request.
        ("production", "false", False),
        ("development", "true", True),
    ],
)
async def test_session_cookie_secure_flag(
    auth_client, env, cookie_secure_override, expect_secure
):
    import os

    from app.core.config import get_settings

    previous_env = os.environ.get("ENV")
    previous_cookie_secure = os.environ.get("COOKIE_SECURE")
    os.environ["ENV"] = env
    if cookie_secure_override is None:
        os.environ.pop("COOKIE_SECURE", None)
    else:
        os.environ["COOKIE_SECURE"] = cookie_secure_override
    get_settings.cache_clear()
    try:
        resp = await auth_client.post(
            "/api/auth/register",
            json={"email": f"cookietest-{env}-{cookie_secure_override}@example.com", "password": "supersecret1"},
        )
        assert resp.status_code == 201
        set_cookie = resp.headers.get("set-cookie", "")
        assert ("Secure" in set_cookie) is expect_secure
    finally:
        if previous_env is None:
            os.environ.pop("ENV", None)
        else:
            os.environ["ENV"] = previous_env
        if previous_cookie_secure is None:
            os.environ.pop("COOKIE_SECURE", None)
        else:
            os.environ["COOKIE_SECURE"] = previous_cookie_secure
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_register_sets_session_cookie_and_returns_user(auth_client):
    resp = await auth_client.post(
        "/api/auth/register",
        json={"email": "New@Example.com", "password": "supersecret1", "name": "New User"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com"
    assert body["name"] == "New User"
    assert body["is_admin"] is False
    assert "password" not in body and "password_hash" not in body
    assert "access_token" in resp.cookies


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(auth_client):
    payload = {"email": "dup@example.com", "password": "supersecret1"}
    first = await auth_client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = await auth_client.post("/api/auth/register", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password_rejected(auth_client):
    resp = await auth_client.post(
        "/api/auth/register", json={"email": "short@example.com", "password": "short"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_with_correct_credentials_succeeds(auth_client):
    await auth_client.post(
        "/api/auth/register", json={"email": "login@example.com", "password": "supersecret1"}
    )
    await auth_client.post("/api/auth/logout")

    resp = await auth_client.post(
        "/api/auth/login", json={"email": "login@example.com", "password": "supersecret1"}
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "login@example.com"
    assert "access_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_with_wrong_password_rejected(auth_client):
    await auth_client.post(
        "/api/auth/register", json={"email": "wrongpw@example.com", "password": "supersecret1"}
    )

    resp = await auth_client.post(
        "/api/auth/login", json={"email": "wrongpw@example.com", "password": "notthepassword"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_unknown_email_gives_same_error_as_wrong_password(auth_client):
    known = await auth_client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "whatever1"}
    )
    await auth_client.post(
        "/api/auth/register", json={"email": "real@example.com", "password": "supersecret1"}
    )
    unknown_pw = await auth_client.post(
        "/api/auth/login", json={"email": "real@example.com", "password": "wrongwrong"}
    )
    assert known.status_code == unknown_pw.status_code == 422
    assert known.json()["error"]["message"] == unknown_pw.json()["error"]["message"]


@pytest.mark.asyncio
async def test_me_requires_auth(auth_client):
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user_after_login(auth_client):
    await auth_client.post(
        "/api/auth/register", json={"email": "me@example.com", "password": "supersecret1"}
    )
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_logout_clears_session(auth_client):
    await auth_client.post(
        "/api/auth/register", json={"email": "logout@example.com", "password": "supersecret1"}
    )
    logout_resp = await auth_client.post("/api/auth/logout")
    assert logout_resp.status_code == 204

    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password_then_relogin(auth_client):
    await auth_client.post(
        "/api/auth/register", json={"email": "change@example.com", "password": "oldpassword1"}
    )
    resp = await auth_client.post(
        "/api/auth/change-password",
        json={"current_password": "oldpassword1", "new_password": "newpassword1"},
    )
    assert resp.status_code == 204

    await auth_client.post("/api/auth/logout")
    old_login = await auth_client.post(
        "/api/auth/login", json={"email": "change@example.com", "password": "oldpassword1"}
    )
    assert old_login.status_code == 422

    new_login = await auth_client.post(
        "/api/auth/login", json={"email": "change@example.com", "password": "newpassword1"}
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current_rejected(auth_client):
    await auth_client.post(
        "/api/auth/register", json={"email": "wrongcur@example.com", "password": "supersecret1"}
    )
    resp = await auth_client.post(
        "/api/auth/change-password",
        json={"current_password": "notright", "new_password": "newpassword1"},
    )
    assert resp.status_code == 422
