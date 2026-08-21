"""Этап 11: GET /api/subscription — read-only plan/usage panel.

Uses the same real-cookie-auth harness as test_api_auth.py (not the
auth-override api_client fixture) since ensure_free_subscription is only
exercised through the real /api/auth/register flow.
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


@pytest_asyncio.fixture
async def sub_client() -> AsyncIterator[AsyncClient]:
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
async def test_requires_auth(sub_client):
    resp = await sub_client.get("/api/subscription")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_new_user_gets_free_plan_with_zero_usage(sub_client):
    await sub_client.post(
        "/api/auth/register", json={"email": "sub1@example.com", "password": "supersecret1"}
    )
    resp = await sub_client.get("/api/subscription")
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan_name"] == "Free"
    assert body["max_search_profiles"] == 3
    assert body["max_sources_per_profile"] == 10
    assert body["max_ai_analyses_per_month"] == 1000
    assert body["price"] is None
    assert body["search_profiles_used"] == 0
    assert body["ai_analyses_used_this_period"] == 0


@pytest.mark.asyncio
async def test_search_profiles_used_reflects_created_profiles(sub_client):
    await sub_client.post(
        "/api/auth/register", json={"email": "sub2@example.com", "password": "supersecret1"}
    )
    await sub_client.post(
        "/api/search-profiles", json={"name": "Веб-разработка", "services": []}
    )
    await sub_client.post(
        "/api/search-profiles", json={"name": "Дизайн", "services": []}
    )

    resp = await sub_client.get("/api/subscription")
    assert resp.status_code == 200
    assert resp.json()["search_profiles_used"] == 2


@pytest.mark.asyncio
async def test_two_users_get_independent_subscriptions(sub_client):
    await sub_client.post(
        "/api/auth/register", json={"email": "usera@example.com", "password": "supersecret1"}
    )
    await sub_client.post("/api/search-profiles", json={"name": "A", "services": []})
    await sub_client.post("/api/auth/logout")

    await sub_client.post(
        "/api/auth/register", json={"email": "userb@example.com", "password": "supersecret1"}
    )
    resp = await sub_client.get("/api/subscription")
    assert resp.json()["search_profiles_used"] == 0
