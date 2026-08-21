"""Этап 12: /api/legal (public) + /api/admin/legal (admin CRUD).

api_client's seeded user is already is_admin=True (see conftest.py), so
these run as an admin session throughout except the explicit
non-admin-is-forbidden check, which registers its own real (non-admin)
user via the app's actual auth flow.
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


@pytest.mark.asyncio
async def test_get_active_returns_404_when_nothing_published(api_client):
    resp = await api_client.get("/api/legal/privacy_policy")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_active_unknown_type_404s(api_client):
    resp = await api_client.get("/api/legal/not_a_real_type")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_create_and_publish_flow(api_client):
    create_resp = await api_client.post(
        "/api/admin/legal",
        json={
            "type": "privacy_policy",
            "version": "0.1-draft",
            "title": "Политика обработки персональных данных",
            "content": "Черновик текста политики.",
        },
    )
    assert create_resp.status_code == 201
    doc_id = create_resp.json()["id"]
    assert create_resp.json()["is_active"] is False

    # Not active yet — public endpoint still 404s.
    assert (await api_client.get("/api/legal/privacy_policy")).status_code == 404

    publish_resp = await api_client.post(f"/api/admin/legal/{doc_id}/publish")
    assert publish_resp.status_code == 200
    assert publish_resp.json()["is_active"] is True

    public_resp = await api_client.get("/api/legal/privacy_policy")
    assert public_resp.status_code == 200
    assert public_resp.json()["version"] == "0.1-draft"


@pytest.mark.asyncio
async def test_publishing_new_version_deactivates_old(api_client):
    v1 = (
        await api_client.post(
            "/api/admin/legal",
            json={"type": "terms_of_service", "version": "1", "title": "T", "content": "v1"},
        )
    ).json()
    await api_client.post(f"/api/admin/legal/{v1['id']}/publish")

    v2 = (
        await api_client.post(
            "/api/admin/legal",
            json={"type": "terms_of_service", "version": "2", "title": "T", "content": "v2"},
        )
    ).json()
    await api_client.post(f"/api/admin/legal/{v2['id']}/publish")

    active = (await api_client.get("/api/legal/terms_of_service")).json()
    assert active["version"] == "2"

    versions = (await api_client.get("/api/admin/legal/terms_of_service")).json()
    active_count = sum(1 for v in versions if v["is_active"])
    assert active_count == 1


@pytest_asyncio.fixture
async def non_admin_client() -> AsyncIterator[AsyncClient]:
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
        await client.post(
            "/api/auth/register",
            json={"email": "notadmin@example.com", "password": "supersecret1"},
        )
        yield client

    app.dependency_overrides.pop(get_db_session, None)
    await engine.dispose()

    if previous_secret is None:
        os.environ.pop("JWT_SECRET", None)
    else:
        os.environ["JWT_SECRET"] = previous_secret
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_non_admin_cannot_manage_legal_documents(non_admin_client):
    resp = await non_admin_client.post(
        "/api/admin/legal",
        json={"type": "cookie_policy", "version": "1", "title": "T", "content": "c"},
    )
    assert resp.status_code == 403
