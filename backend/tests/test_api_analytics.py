"""Stage 9/11: /api/analytics/overview."""
import datetime as dt

import pytest

from app.models.enums import SourceType
from app.models.search_profile import SearchProfile
from app.models.user import User
from app.repositories.lead_repository import LeadRepository
from app.repositories.raw_item_repository import RawItemRepository
from app.repositories.source_repository import SourceRepository


async def _seed_lead(
    api_db, search_profile_id: int, score: int, status: str = "new", created_at=None
) -> None:
    async with api_db() as session:
        source_repo = SourceRepository(session)
        raw_repo = RawItemRepository(session)
        lead_repo = LeadRepository(session)

        source = await source_repo.create(name="C", type=SourceType.TELEGRAM.value, external_identifier="c")
        raw_item = await raw_repo.create(
            source_id=source.id, external_id=f"e-{score}-{status}-{created_at}",
            text="t", content_hash=f"h-{score}-{status}-{created_at}",
        )
        lead = await lead_repo.create(
            raw_item_id=raw_item.id, search_profile_id=search_profile_id,
            lead_score=score, status=status,
            services=[], positive_signals=[], negative_signals=[],
        )
        if created_at is not None:
            lead.created_at = created_at
            await session.flush()
        await session.commit()


@pytest.mark.asyncio
async def test_overview_counts(api_client, api_db, test_search_profile_id):
    await _seed_lead(api_db, test_search_profile_id, score=80, status="new")
    await _seed_lead(api_db, test_search_profile_id, score=30, status="new")
    await _seed_lead(api_db, test_search_profile_id, score=95, status="converted")

    resp = await api_client.get("/api/analytics/overview")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_leads"] == 3
    assert body["hot_leads"] == 2  # score >= NOTIFICATION_THRESHOLD (60 default)
    assert body["converted_leads"] == 1
    assert body["today_leads"] == 3  # all created "now"


@pytest.mark.asyncio
async def test_overview_includes_7_and_30_day_series(api_client, api_db, test_search_profile_id):
    await _seed_lead(api_db, test_search_profile_id, score=50)

    resp = await api_client.get("/api/analytics/overview")
    body = resp.json()

    assert len(body["leads_last_7_days"]) == 7
    assert len(body["leads_last_30_days"]) == 30
    assert sum(day["count"] for day in body["leads_last_7_days"]) == 1


@pytest.mark.asyncio
async def test_overview_with_no_leads_returns_zeros(api_client):
    resp = await api_client.get("/api/analytics/overview")
    body = resp.json()
    assert body["total_leads"] == 0
    assert body["hot_leads"] == 0
    assert all(day["count"] == 0 for day in body["leads_last_7_days"])


@pytest.mark.asyncio
async def test_overview_does_not_leak_another_profiles_leads(
    api_client, api_db, test_search_profile_id
):
    """Isolation regression check: leads seeded under a different
    SearchProfile must never appear in this user's aggregate stats — see
    the search_profile_id-scoping fix in app/services/lead_stats.py."""
    async with api_db() as session:
        other_user = User(email="other@example.com", password_hash="x")
        session.add(other_user)
        await session.flush()
        other_profile = SearchProfile(user_id=other_user.id, name="Other profile")
        session.add(other_profile)
        await session.commit()
        other_profile_id = other_profile.id

    await _seed_lead(api_db, other_profile_id, score=95, status="new")
    await _seed_lead(api_db, test_search_profile_id, score=80, status="new")

    resp = await api_client.get("/api/analytics/overview")
    body = resp.json()

    assert body["total_leads"] == 1
    assert body["hot_leads"] == 1


@pytest.mark.asyncio
async def test_overview_with_no_search_profile_returns_zeros_not_global_stats(
    api_client, api_db, test_search_profile_id
):
    """A signed-in user with no SearchProfile yet (onboarding incomplete)
    must see all-zeros, never another tenant's aggregate leads — the
    search_profile_id=None sentinel in LeadStatsService means "unscoped"
    (used by the bot), so the endpoint must special-case this rather than
    passing it through."""
    from app.core.security import get_current_user
    from app.main import app

    async with api_db() as session:
        profileless_user = User(email="noprofile@example.com", password_hash="x")
        session.add(profileless_user)
        await session.commit()
        profileless_user_id = profileless_user.id

    await _seed_lead(api_db, test_search_profile_id, score=90, status="new")

    async def override_profileless_user() -> User:
        async with api_db() as session:
            return await session.get(User, profileless_user_id)

    # api_client's own fixture teardown pops this override afterwards, so
    # no need to restore it — nothing else in this test depends on it.
    app.dependency_overrides[get_current_user] = override_profileless_user
    resp = await api_client.get("/api/analytics/overview")

    body = resp.json()
    assert body["total_leads"] == 0
    assert body["hot_leads"] == 0
    assert len(body["leads_last_7_days"]) == 7
    assert all(day["count"] == 0 for day in body["leads_last_7_days"])


@pytest.mark.asyncio
async def test_explicit_search_profile_id_selects_the_right_profile(
    api_client, api_db, test_search_profile_id
):
    """Этап 2: a user with more than one SearchProfile must be able to ask
    for a SPECIFIC one's stats, not just always get "the first" one."""
    async with api_db() as session:
        second_profile = SearchProfile(user_id=1, name="Second search")
        session.add(second_profile)
        await session.commit()
        second_profile_id = second_profile.id

    await _seed_lead(api_db, test_search_profile_id, score=50)
    await _seed_lead(api_db, second_profile_id, score=90)
    await _seed_lead(api_db, second_profile_id, score=95)

    default_resp = await api_client.get("/api/analytics/overview")
    assert default_resp.json()["total_leads"] == 1

    explicit_resp = await api_client.get(
        "/api/analytics/overview", params={"search_profile_id": second_profile_id}
    )
    assert explicit_resp.json()["total_leads"] == 2


@pytest.mark.asyncio
async def test_search_profile_id_param_rejects_foreign_profile(api_client, api_db):
    async with api_db() as session:
        other_user = User(email="foreign-analytics@example.com", password_hash="x")
        session.add(other_user)
        await session.flush()
        other_profile = SearchProfile(user_id=other_user.id, name="Not yours")
        session.add(other_profile)
        await session.commit()
        other_profile_id = other_profile.id

    resp = await api_client.get(
        "/api/analytics/overview", params={"search_profile_id": other_profile_id}
    )
    assert resp.status_code == 404
