"""/api/admin — system-wide overview + user management, admin-only."""
import pytest

from app.models.audit_log import AuditLog
from app.models.enums import SourceType
from app.models.search_profile import SearchProfile
from app.models.search_profile_keyword import SearchProfileKeyword
from app.models.search_profile_source import SearchProfileSource
from app.models.user import User
from app.repositories.lead_repository import LeadRepository
from app.repositories.raw_item_repository import RawItemRepository
from app.repositories.source_repository import SourceRepository


async def _seed_lead(api_db, search_profile_id: int, score: int = 50) -> None:
    async with api_db() as session:
        source_repo = SourceRepository(session)
        raw_repo = RawItemRepository(session)
        lead_repo = LeadRepository(session)
        source = await source_repo.create(
            name="Chan", type=SourceType.TELEGRAM.value, external_identifier=f"c-{score}"
        )
        raw_item = await raw_repo.create(
            source_id=source.id, external_id=f"e-{score}", text="t", content_hash=f"h-{score}"
        )
        await lead_repo.create(
            raw_item_id=raw_item.id,
            search_profile_id=search_profile_id,
            lead_score=score,
            services=[],
            positive_signals=[],
            negative_signals=[],
        )
        await session.commit()


@pytest.mark.asyncio
async def test_overview_counts_across_all_users(api_client, api_db, test_search_profile_id):
    await _seed_lead(api_db, test_search_profile_id, score=80)

    async with api_db() as session:
        other_user = User(email="other@example.com", password_hash="x")
        session.add(other_user)
        await session.flush()
        other_profile = SearchProfile(user_id=other_user.id, name="Other")
        session.add(other_profile)
        await session.commit()
        other_profile_id = other_profile.id

    await _seed_lead(api_db, other_profile_id, score=90)

    resp = await api_client.get("/api/admin/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_users"] == 2
    assert body["total_search_profiles"] == 2
    assert body["total_leads"] == 2
    assert body["database_status"] == "ok"


@pytest.mark.asyncio
async def test_list_users_includes_per_user_counts(api_client, api_db, test_search_profile_id):
    await _seed_lead(api_db, test_search_profile_id, score=70)
    await _seed_lead(api_db, test_search_profile_id, score=75)

    resp = await api_client.get("/api/admin/users")
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) == 1
    assert users[0]["email"] == "test@example.com"
    assert users[0]["search_profile_count"] == 1
    assert users[0]["lead_count"] == 2


@pytest.mark.asyncio
async def test_non_admin_forbidden(api_client, api_db, test_search_profile_id):
    from app.core.security import get_current_user
    from app.main import app

    async with api_db() as session:
        regular_user = User(email="regular@example.com", password_hash="x", is_admin=False)
        session.add(regular_user)
        await session.commit()
        regular_user_id = regular_user.id

    async def override_regular_user() -> User:
        async with api_db() as session:
            return await session.get(User, regular_user_id)

    app.dependency_overrides[get_current_user] = override_regular_user

    resp = await api_client.get("/api/admin/overview")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_toggle_user_admin_status(api_client, api_db, test_search_profile_id):
    async with api_db() as session:
        target = User(email="promote-me@example.com", password_hash="x", is_admin=False)
        session.add(target)
        await session.commit()
        target_id = target.id

    resp = await api_client.patch(f"/api/admin/users/{target_id}", json={"is_admin": True})
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is True


@pytest.mark.asyncio
async def test_admin_cannot_demote_self(api_client, api_db, test_search_profile_id):
    async with api_db() as session:
        profile = await session.get(SearchProfile, test_search_profile_id)
        self_user_id = profile.user_id

    resp = await api_client.patch(f"/api/admin/users/{self_user_id}", json={"is_admin": False})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_missing_user_404(api_client):
    resp = await api_client.patch("/api/admin/users/9999", json={"is_admin": True})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_users_last_login_at_is_null_without_login_events(
    api_client, test_search_profile_id
):
    resp = await api_client.get("/api/admin/users")
    assert resp.status_code == 200
    assert resp.json()[0]["last_login_at"] is None


@pytest.mark.asyncio
async def test_list_users_last_login_at_reflects_most_recent_login(
    api_client, api_db, test_search_profile_id
):
    async with api_db() as session:
        profile = await session.get(SearchProfile, test_search_profile_id)
        session.add(AuditLog(user_id=profile.user_id, action="login"))
        session.add(AuditLog(user_id=profile.user_id, action="telegram_connect"))
        await session.commit()

    resp = await api_client.get("/api/admin/users")
    assert resp.json()[0]["last_login_at"] is not None


@pytest.mark.asyncio
async def test_get_user_profiles_includes_full_config_and_sources(
    api_client, api_db, test_search_profile_id
):
    async with api_db() as session:
        profile = await session.get(SearchProfile, test_search_profile_id)
        profile.profession = "Веб-дизайнер"
        profile.services = ["веб-дизайн", "лендинги"]
        profile.preferred_niches = ["e-commerce"]
        profile.excluded_niches = ["вакансии"]
        user_id = profile.user_id

        source_repo = SourceRepository(session)
        catalog_source = await source_repo.create(
            name="Catalog channel", type=SourceType.TELEGRAM.value, external_identifier="cat-1"
        )
        custom_source = await source_repo.create(
            name="My own channel",
            type=SourceType.TELEGRAM.value,
            external_identifier="custom-1",
            added_by_user_id=user_id,
        )
        session.add_all(
            [
                SearchProfileSource(
                    search_profile_id=profile.id, source_id=catalog_source.id, enabled=True
                ),
                SearchProfileSource(
                    search_profile_id=profile.id, source_id=custom_source.id, enabled=True
                ),
                SearchProfileKeyword(
                    search_profile_id=profile.id,
                    text="нужен сайт",
                    category="direct_intent",
                    enabled=True,
                ),
            ]
        )
        await session.commit()

    resp = await api_client.get(f"/api/admin/users/{user_id}/profiles")
    assert resp.status_code == 200
    profiles = resp.json()
    assert len(profiles) == 1
    detail = profiles[0]
    assert detail["profession"] == "Веб-дизайнер"
    assert detail["services"] == ["веб-дизайн", "лендинги"]
    assert detail["preferred_niches"] == ["e-commerce"]
    assert detail["excluded_niches"] == ["вакансии"]

    sources_by_name = {s["name"]: s for s in detail["sources"]}
    assert sources_by_name["Catalog channel"]["is_custom"] is False
    assert sources_by_name["My own channel"]["is_custom"] is True

    assert len(detail["keywords"]) == 1
    assert detail["keywords"][0]["text"] == "нужен сайт"


@pytest.mark.asyncio
async def test_get_user_profiles_missing_user_404(api_client):
    resp = await api_client.get("/api/admin/users/9999/profiles")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_user_profiles_forbidden_for_non_admin(api_client, api_db, test_search_profile_id):
    from app.core.security import get_current_user
    from app.main import app

    async with api_db() as session:
        regular_user = User(email="regular2@example.com", password_hash="x", is_admin=False)
        session.add(regular_user)
        await session.commit()
        regular_user_id = regular_user.id

    async def override_regular_user() -> User:
        async with api_db() as session:
            return await session.get(User, regular_user_id)

    app.dependency_overrides[get_current_user] = override_regular_user

    resp = await api_client.get(f"/api/admin/users/{regular_user_id}/profiles")
    assert resp.status_code == 403
