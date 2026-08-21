"""Bot-initiated "Войти через Telegram" flow — /api/auth/telegram/*.

The bot's own /start handler isn't exercised here (that's aiogram-side,
covered by not crashing on import); this simulates "the user tapped the
deep link" by calling telegram_login_service.confirm() directly against
the same test DB the API client is wired to, which is exactly what the
bot handler does under the hood.
"""
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
from app.models.enums import TelegramTokenPurpose


@pytest_asyncio.fixture
async def telegram_client():
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
    _attempts.clear()

    previous_secret = os.environ.get("JWT_SECRET")
    previous_bot_username = os.environ.get("TELEGRAM_BOT_USERNAME")
    os.environ["JWT_SECRET"] = "test-secret-do-not-use-in-prod"
    os.environ["TELEGRAM_BOT_USERNAME"] = "readhunter_test_bot"
    get_settings.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, session_factory

    app.dependency_overrides.pop(get_db_session, None)
    await engine.dispose()

    if previous_secret is None:
        os.environ.pop("JWT_SECRET", None)
    else:
        os.environ["JWT_SECRET"] = previous_secret
    if previous_bot_username is None:
        os.environ.pop("TELEGRAM_BOT_USERNAME", None)
    else:
        os.environ["TELEGRAM_BOT_USERNAME"] = previous_bot_username
    get_settings.cache_clear()


def _extract_payload(deep_link: str) -> str:
    return deep_link.split("?start=", 1)[1]


async def _confirm_as_bot(session_factory, payload: str, telegram_id: int, username: str = "tguser"):
    from app.services.telegram_login_service import confirm

    async with session_factory() as session:
        ok = await confirm(
            session, payload, telegram_id=telegram_id, telegram_username=username, telegram_first_name="Test"
        )
        return ok


@pytest.mark.asyncio
async def test_start_returns_deep_link_with_bot_username(telegram_client):
    client, _ = telegram_client
    resp = await client.post("/api/auth/telegram/start")
    assert resp.status_code == 200
    body = resp.json()
    assert body["deep_link"].startswith("https://t.me/readhunter_test_bot?start=login-")
    assert body["token"]


@pytest.mark.asyncio
async def test_status_is_pending_before_bot_confirms(telegram_client):
    client, _ = telegram_client
    start = (await client.post("/api/auth/telegram/start")).json()
    resp = await client.get("/api/auth/telegram/status", params={"token": start["token"]})
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_full_login_flow_creates_new_user(telegram_client):
    client, session_factory = telegram_client
    start = (await client.post("/api/auth/telegram/start")).json()
    payload = _extract_payload(start["deep_link"])

    ok = await _confirm_as_bot(session_factory, payload, telegram_id=111222333, username="newbie")
    assert ok is True

    status_resp = await client.get("/api/auth/telegram/status", params={"token": start["token"]})
    assert status_resp.json()["status"] == "confirmed"

    complete_resp = await client.post(
        "/api/auth/telegram/complete", json={"token": start["token"], "accept_legal": True}
    )
    assert complete_resp.status_code == 200
    body = complete_resp.json()
    assert body["telegram_username"] == "newbie"
    assert body["has_telegram"] is True
    assert body["has_password"] is False
    assert body["email"] is None
    assert "access_token" in complete_resp.cookies

    me_resp = await client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["telegram_username"] == "newbie"


@pytest.mark.asyncio
async def test_second_login_finds_same_user_not_a_duplicate(telegram_client):
    client, session_factory = telegram_client
    start1 = (await client.post("/api/auth/telegram/start")).json()
    payload1 = _extract_payload(start1["deep_link"])
    await _confirm_as_bot(session_factory, payload1, telegram_id=555, username="returning")
    first = await client.post(
        "/api/auth/telegram/complete", json={"token": start1["token"], "accept_legal": True}
    )
    first_id = first.json()["id"]
    await client.post("/api/auth/logout")

    start2 = (await client.post("/api/auth/telegram/start")).json()
    payload2 = _extract_payload(start2["deep_link"])
    await _confirm_as_bot(session_factory, payload2, telegram_id=555, username="returning")
    second = await client.post("/api/auth/telegram/complete", json={"token": start2["token"]})

    assert second.status_code == 200
    assert second.json()["id"] == first_id


@pytest.mark.asyncio
async def test_complete_before_confirm_rejected(telegram_client):
    client, _ = telegram_client
    start = (await client.post("/api/auth/telegram/start")).json()
    resp = await client.post("/api/auth/telegram/complete", json={"token": start["token"]})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_token_is_single_use(telegram_client):
    client, session_factory = telegram_client
    start = (await client.post("/api/auth/telegram/start")).json()
    payload = _extract_payload(start["deep_link"])
    await _confirm_as_bot(session_factory, payload, telegram_id=999)

    first = await client.post(
        "/api/auth/telegram/complete", json={"token": start["token"], "accept_legal": True}
    )
    assert first.status_code == 200

    second = await client.post("/api/auth/telegram/complete", json={"token": start["token"]})
    assert second.status_code == 422


@pytest.mark.asyncio
async def test_link_requires_auth(telegram_client):
    client, _ = telegram_client
    resp = await client.post("/api/auth/telegram/link/start")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_link_attaches_telegram_to_existing_email_account(telegram_client):
    client, session_factory = telegram_client
    await client.post(
        "/api/auth/register",
        json={"email": "linkme@example.com", "password": "supersecret1", "accept_legal": True},
    )

    start = (await client.post("/api/auth/telegram/link/start")).json()
    payload = _extract_payload(start["deep_link"])
    assert payload.startswith("link-")
    await _confirm_as_bot(session_factory, payload, telegram_id=777888, username="linked_user")

    complete_resp = await client.post("/api/auth/telegram/complete", json={"token": start["token"]})
    assert complete_resp.status_code == 200
    body = complete_resp.json()
    assert body["email"] == "linkme@example.com"
    assert body["telegram_username"] == "linked_user"
    assert body["has_telegram"] is True
    assert body["has_password"] is True


@pytest.mark.asyncio
async def test_link_token_cannot_be_completed_by_a_different_session(telegram_client):
    client, session_factory = telegram_client
    await client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "supersecret1", "accept_legal": True},
    )
    start = (await client.post("/api/auth/telegram/link/start")).json()
    payload = _extract_payload(start["deep_link"])
    await _confirm_as_bot(session_factory, payload, telegram_id=424242)

    await client.post("/api/auth/logout")
    await client.post(
        "/api/auth/register",
        json={"email": "attacker@example.com", "password": "supersecret1", "accept_legal": True},
    )

    resp = await client.post("/api/auth/telegram/complete", json={"token": start["token"]})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_telegram_id_cannot_be_linked_to_two_accounts(telegram_client):
    client, session_factory = telegram_client
    await client.post(
        "/api/auth/register",
        json={"email": "first@example.com", "password": "supersecret1", "accept_legal": True},
    )
    start1 = (await client.post("/api/auth/telegram/link/start")).json()
    await _confirm_as_bot(session_factory, _extract_payload(start1["deep_link"]), telegram_id=1010)
    await client.post("/api/auth/telegram/complete", json={"token": start1["token"]})
    await client.post("/api/auth/logout")

    await client.post(
        "/api/auth/register",
        json={"email": "second@example.com", "password": "supersecret1", "accept_legal": True},
    )
    start2 = (await client.post("/api/auth/telegram/link/start")).json()
    await _confirm_as_bot(session_factory, _extract_payload(start2["deep_link"]), telegram_id=1010)
    resp = await client.post("/api/auth/telegram/complete", json={"token": start2["token"]})
    assert resp.status_code == 422
