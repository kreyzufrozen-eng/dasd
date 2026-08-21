"""Этап 12 (legal/privacy layer): /api/auth/delete-account and
/api/auth/export-data."""
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
async def account_client() -> AsyncIterator[AsyncClient]:
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
async def test_export_requires_auth(account_client):
    resp = await account_client.get("/api/auth/export-data")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_export_returns_account_and_profiles(account_client):
    await account_client.post(
        "/api/auth/register",
        json={"email": "exportme@example.com", "password": "supersecret1"},
    )
    await account_client.post("/api/search-profiles", json={"name": "Веб", "services": []})

    resp = await account_client.get("/api/auth/export-data")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert "attachment" in resp.headers["content-disposition"]
    body = resp.json()
    assert body["account"]["email"] == "exportme@example.com"
    assert len(body["search_profiles"]) == 1
    assert body["search_profiles"][0]["name"] == "Веб"


@pytest.mark.asyncio
async def test_delete_account_requires_confirm(account_client):
    await account_client.post(
        "/api/auth/register",
        json={"email": "delnoconfirm@example.com", "password": "supersecret1"},
    )
    resp = await account_client.post(
        "/api/auth/delete-account", json={"password": "supersecret1", "confirm": False}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_account_requires_correct_password(account_client):
    await account_client.post(
        "/api/auth/register",
        json={"email": "delwrongpw@example.com", "password": "supersecret1"},
    )
    resp = await account_client.post(
        "/api/auth/delete-account", json={"password": "wrongwrong", "confirm": True}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_account_succeeds_and_clears_session(account_client):
    await account_client.post(
        "/api/auth/register",
        json={"email": "deleteme@example.com", "password": "supersecret1"},
    )
    resp = await account_client.post(
        "/api/auth/delete-account", json={"password": "supersecret1", "confirm": True}
    )
    assert resp.status_code == 204

    me_resp = await account_client.get("/api/auth/me")
    assert me_resp.status_code == 401

    login_resp = await account_client.post(
        "/api/auth/login", json={"email": "deleteme@example.com", "password": "supersecret1"}
    )
    assert login_resp.status_code == 422
