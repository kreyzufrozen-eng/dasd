"""Этап 2: /api/search-profiles/{id}/sources and /api/sources/catalog."""
import pytest

from app.models.enums import SourceType
from app.repositories.source_repository import SourceRepository


async def _seed_source(api_db, name: str = "Chan", category: str = "development") -> int:
    async with api_db() as session:
        source_repo = SourceRepository(session)
        source = await source_repo.create(
            name=name,
            type=SourceType.TELEGRAM.value,
            external_identifier=name.lower(),
            category=category,
        )
        await session.commit()
        return source.id


@pytest.mark.asyncio
async def test_list_profile_sources_empty(api_client, test_search_profile_id):
    resp = await api_client.get(f"/api/search-profiles/{test_search_profile_id}/sources")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_attach_existing_source(api_client, api_db, test_search_profile_id):
    source_id = await _seed_source(api_db)

    resp = await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/sources",
        json={"source_id": source_id, "enabled": True},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["source_id"] == source_id
    assert body["enabled"] is True
    assert body["source"]["id"] == source_id

    listed = await api_client.get(f"/api/search-profiles/{test_search_profile_id}/sources")
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_attach_same_source_twice_updates_instead_of_duplicating(
    api_client, api_db, test_search_profile_id
):
    source_id = await _seed_source(api_db)
    await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/sources",
        json={"source_id": source_id, "enabled": True},
    )
    resp = await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/sources",
        json={"source_id": source_id, "enabled": False},
    )
    assert resp.status_code == 201
    assert resp.json()["enabled"] is False

    listed = await api_client.get(f"/api/search-profiles/{test_search_profile_id}/sources")
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_bulk_attach_creates_all_links_in_one_call(
    api_client, api_db, test_search_profile_id
):
    source_ids = [await _seed_source(api_db, name=f"Chan{i}") for i in range(5)]

    resp = await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/sources/bulk",
        json={"source_ids": source_ids},
    )
    assert resp.status_code == 201
    assert resp.json()["attached"] == 5

    listed = await api_client.get(f"/api/search-profiles/{test_search_profile_id}/sources")
    assert len(listed.json()) == 5


@pytest.mark.asyncio
async def test_bulk_attach_skips_already_linked_and_invalid_ids(
    api_client, api_db, test_search_profile_id
):
    source_ids = [await _seed_source(api_db, name=f"Bulk{i}") for i in range(3)]
    # Pre-link the first one directly.
    await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/sources",
        json={"source_id": source_ids[0], "enabled": True},
    )

    resp = await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/sources/bulk",
        json={"source_ids": source_ids + [999999]},  # + one nonexistent id
    )
    assert resp.status_code == 201
    # Only the 2 not-yet-linked, valid ids get created.
    assert resp.json()["attached"] == 2

    listed = await api_client.get(f"/api/search-profiles/{test_search_profile_id}/sources")
    assert len(listed.json()) == 3


@pytest.mark.asyncio
async def test_bulk_attach_empty_list_is_a_noop(api_client, test_search_profile_id):
    resp = await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/sources/bulk",
        json={"source_ids": []},
    )
    assert resp.status_code == 201
    assert resp.json()["attached"] == 0


@pytest.mark.asyncio
async def test_bulk_attach_404s_for_foreign_profile(api_client):
    resp = await api_client.post(
        "/api/search-profiles/9999/sources/bulk", json={"source_ids": [1]}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_custom_source_dedups_by_type_and_identifier(
    api_client, api_db, test_search_profile_id
):
    payload = {
        "name": "My chat",
        "type": "telegram",
        "url": "https://t.me/my_chat",
        "external_identifier": "my_chat",
    }
    first = await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/sources/custom", json=payload
    )
    assert first.status_code == 201
    first_source_id = first.json()["source_id"]

    async with api_db() as session:
        other_user = None
        from app.models.search_profile import SearchProfile
        from app.models.user import User

        other_user = User(email="dedup-test@example.com", password_hash="x")
        session.add(other_user)
        await session.flush()
        other_profile = SearchProfile(user_id=other_user.id, name="Other")
        session.add(other_profile)
        await session.commit()
        other_profile_id = other_profile.id

    from app.core.security import get_current_user
    from app.main import app

    async def override_other_user():
        async with api_db() as session:
            return await session.get(User, other_user.id)

    app.dependency_overrides[get_current_user] = override_other_user
    second = await api_client.post(
        f"/api/search-profiles/{other_profile_id}/sources/custom", json=payload
    )
    assert second.status_code == 201
    assert second.json()["source_id"] == first_source_id


@pytest.mark.asyncio
async def test_update_and_detach_profile_source(api_client, api_db, test_search_profile_id):
    source_id = await _seed_source(api_db)
    await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/sources",
        json={"source_id": source_id, "enabled": True},
    )

    patch_resp = await api_client.patch(
        f"/api/search-profiles/{test_search_profile_id}/sources/{source_id}",
        json={"enabled": False},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["enabled"] is False

    delete_resp = await api_client.delete(
        f"/api/search-profiles/{test_search_profile_id}/sources/{source_id}"
    )
    assert delete_resp.status_code == 204

    listed = await api_client.get(f"/api/search-profiles/{test_search_profile_id}/sources")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_sources_endpoints_404_for_foreign_profile(api_client):
    resp = await api_client.get("/api/search-profiles/9999/sources")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_catalog_lists_sources_with_category_and_link_state(
    api_client, api_db, test_search_profile_id
):
    source_id = await _seed_source(api_db, name="DesignChan", category="design")
    await _seed_source(api_db, name="DevChan", category="development")

    await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/sources",
        json={"source_id": source_id, "enabled": True},
    )

    resp = await api_client.get(
        "/api/sources/catalog", params={"search_profile_id": test_search_profile_id}
    )
    assert resp.status_code == 200
    entries = {e["id"]: e for e in resp.json()}
    assert entries[source_id]["already_added"] is True
    assert entries[source_id]["enabled_for_profile"] is True

    filtered = await api_client.get("/api/sources/catalog", params={"category": "design"})
    assert all(e["category"] == "design" for e in filtered.json())


@pytest.mark.asyncio
async def test_catalog_without_profile_id_shows_unlinked_state(api_client, api_db):
    await _seed_source(api_db)
    resp = await api_client.get("/api/sources/catalog")
    assert resp.status_code == 200
    assert all(e["already_added"] is False for e in resp.json())
