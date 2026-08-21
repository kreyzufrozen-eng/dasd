"""Этап 10: GET /api/search-profiles/{id}/analytics — funnel + breakdown."""
import pytest

from app.models.enums import SourceType
from app.repositories.lead_repository import LeadRepository
from app.repositories.raw_item_repository import RawItemRepository
from app.repositories.source_repository import SourceRepository


async def _get_or_create_source(session, source_name: str) -> int:
    source_repo = SourceRepository(session)
    existing = await source_repo.get_by_type_and_identifier(SourceType.TELEGRAM.value, source_name)
    if existing:
        return existing.id
    source = await source_repo.create(
        name=source_name, type=SourceType.TELEGRAM.value, external_identifier=source_name
    )
    return source.id


async def _seed_lead(
    api_db,
    search_profile_id: int,
    score: int,
    is_lead: bool = True,
    business_niche=None,
    budget_min=None,
    budget_max=None,
    currency=None,
    source_name: str = "Chan",
) -> None:
    async with api_db() as session:
        raw_repo = RawItemRepository(session)
        lead_repo = LeadRepository(session)

        source_id = await _get_or_create_source(session, source_name)
        raw_item = await raw_repo.create(
            source_id=source_id, external_id=f"e-{score}-{source_name}", text="t",
            content_hash=f"h-{score}-{source_name}",
        )
        await lead_repo.create(
            raw_item_id=raw_item.id, search_profile_id=search_profile_id,
            lead_score=score, is_lead=is_lead, business_niche=business_niche,
            budget_min=budget_min, budget_max=budget_max, currency=currency,
            services=[], positive_signals=[], negative_signals=[],
        )
        await session.commit()


@pytest.mark.asyncio
async def test_funnel_counts(api_client, api_db, test_search_profile_id):
    await _seed_lead(api_db, test_search_profile_id, score=90, is_lead=True)
    await _seed_lead(api_db, test_search_profile_id, score=30, is_lead=False)
    await _seed_lead(api_db, test_search_profile_id, score=20, is_lead=False)

    resp = await api_client.get(
        f"/api/search-profiles/{test_search_profile_id}/analytics", params={"period": "all"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["funnel"]["candidates"] == 3
    assert body["funnel"]["leads"] == 1
    assert body["funnel"]["hot_leads"] == 1  # score >= 60 default threshold


@pytest.mark.asyncio
async def test_top_sources_and_niches(api_client, api_db, test_search_profile_id):
    await _seed_lead(
        api_db, test_search_profile_id, score=80, business_niche="dentistry", source_name="A"
    )
    await _seed_lead(
        api_db, test_search_profile_id, score=85, business_niche="dentistry", source_name="A"
    )
    await _seed_lead(
        api_db, test_search_profile_id, score=70, business_niche="retail", source_name="B"
    )

    resp = await api_client.get(
        f"/api/search-profiles/{test_search_profile_id}/analytics", params={"period": "all"}
    )
    body = resp.json()

    assert body["top_sources"][0]["source_name"] == "A"
    assert body["top_sources"][0]["lead_count"] == 2
    assert body["top_niches"][0]["niche"] == "dentistry"
    assert body["top_niches"][0]["lead_count"] == 2


@pytest.mark.asyncio
async def test_avg_budget_only_counts_leads_with_budget(api_client, api_db, test_search_profile_id):
    await _seed_lead(
        api_db, test_search_profile_id, score=80, budget_min=50000, budget_max=100000, currency="RUB"
    )
    await _seed_lead(api_db, test_search_profile_id, score=70)  # no budget

    resp = await api_client.get(
        f"/api/search-profiles/{test_search_profile_id}/analytics", params={"period": "all"}
    )
    body = resp.json()
    assert body["avg_budget"] == 75000.0
    assert body["budget_currency"] == "RUB"


@pytest.mark.asyncio
async def test_isolated_from_other_profiles(api_client, api_db, test_search_profile_id):
    async with api_db() as session:
        from app.models.search_profile import SearchProfile
        from app.models.user import User

        other_user = User(email="other-analytics@example.com", password_hash="x")
        session.add(other_user)
        await session.flush()
        other_profile = SearchProfile(user_id=other_user.id, name="Other")
        session.add(other_profile)
        await session.commit()
        other_profile_id = other_profile.id

    await _seed_lead(api_db, other_profile_id, score=95)
    await _seed_lead(api_db, test_search_profile_id, score=80)

    resp = await api_client.get(
        f"/api/search-profiles/{test_search_profile_id}/analytics", params={"period": "all"}
    )
    body = resp.json()
    assert body["funnel"]["candidates"] == 1


@pytest.mark.asyncio
async def test_404_for_foreign_profile(api_client, api_db):
    async with api_db() as session:
        from app.models.search_profile import SearchProfile
        from app.models.user import User

        other_user = User(email="foreign-pa@example.com", password_hash="x")
        session.add(other_user)
        await session.flush()
        other_profile = SearchProfile(user_id=other_user.id, name="Not yours")
        session.add(other_profile)
        await session.commit()
        other_profile_id = other_profile.id

    resp = await api_client.get(f"/api/search-profiles/{other_profile_id}/analytics")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_empty_profile_returns_zeros_not_error(api_client, test_search_profile_id):
    resp = await api_client.get(
        f"/api/search-profiles/{test_search_profile_id}/analytics", params={"period": "all"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["funnel"] == {"candidates": 0, "leads": 0, "hot_leads": 0}
    assert body["avg_budget"] is None
    assert body["top_sources"] == []
