"""Shared pytest fixtures.

Uses an in-memory SQLite (aiosqlite) database for all model/repository
tests instead of requiring a real Postgres — this is what lets the test
suite run in any environment (including this sandbox, which has no
Postgres/Docker) while still exercising real SQLAlchemy ORM behavior.
JSON columns are declared with the dialect-neutral `sqlalchemy.JSON` type
specifically so this works identically on SQLite and Postgres.
"""
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import (  # noqa: F401
    Keyword,
    Lead,
    LeadFeedback,
    RawItem,
    SearchProfile,
    Source,
    User,
)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def api_db() -> AsyncIterator[async_sessionmaker]:
    """Sessionmaker for an isolated in-memory SQLite DB (StaticPool, so
    every session — including the ones FastAPI opens per-request — sees
    the same data). Exposed separately from api_client so tests can seed
    data directly (there's no API endpoint to create a Lead — those only
    come from the pipeline)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(bind=engine, expire_on_commit=False)

    await engine.dispose()


@pytest_asyncio.fixture
async def test_search_profile_id(api_db: async_sessionmaker) -> int:
    """Seeds the one User + SearchProfile that `api_client`'s
    get_current_user override impersonates, and that Lead-seeding helpers
    in individual test files attach their leads to (Stage 1 made Lead
    N:1 with RawItem, scoped by search_profile_id — see
    PROJECT_AUDIT.md). Fresh in-memory DB per test, so this is always the
    first row: id=1."""
    async with api_db() as session:
        user = User(email="test@example.com", password_hash="x", is_admin=True)
        session.add(user)
        await session.flush()

        profile = SearchProfile(user_id=user.id, name="Test profile")
        session.add(profile)
        await session.commit()
        return profile.id


@pytest_asyncio.fixture
async def api_client(
    api_db: async_sessionmaker, test_search_profile_id: int
) -> AsyncIterator[AsyncClient]:
    """An httpx AsyncClient wired to the real FastAPI app, with the DB
    dependency swapped for the api_db fixture's isolated SQLite DB, and
    both auth layers overridden to act as the seeded test user (see
    test_search_profile_id) — API-key/JWT auth mechanics themselves are
    exercised directly in test_security.py."""
    from app.core.security import get_current_user, verify_api_key
    from app.db.session import get_db_session
    from app.main import app

    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with api_db() as session:
            yield session

    async def override_verify_api_key() -> None:
        return None

    async def override_get_current_user() -> User:
        async with api_db() as session:
            profile = await session.get(SearchProfile, test_search_profile_id)
            return await session.get(User, profile.user_id)

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[verify_api_key] = override_verify_api_key
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(verify_api_key, None)
    app.dependency_overrides.pop(get_current_user, None)
