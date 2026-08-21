"""Этап 2: /api/search-profiles/{id}/keywords."""
import pytest


@pytest.mark.asyncio
async def test_list_profile_keywords_empty(api_client, test_search_profile_id):
    resp = await api_client.get(f"/api/search-profiles/{test_search_profile_id}/keywords")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_profile_keyword(api_client, test_search_profile_id):
    resp = await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/keywords",
        json={"text": "нужен дизайнер карточек", "category": "direct_intent", "weight": 2.0},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["text"] == "нужен дизайнер карточек"
    assert body["category"] == "direct_intent"
    assert body["enabled"] is True
    assert body["keyword_id"] is None


@pytest.mark.asyncio
async def test_create_profile_keyword_rejects_bad_category(api_client, test_search_profile_id):
    resp = await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/keywords",
        json={"text": "x", "category": "not_a_real_category"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_filter_by_category(api_client, test_search_profile_id):
    await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/keywords",
        json={"text": "нужен сайт", "category": "direct_intent"},
    )
    await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/keywords",
        json={"text": "стажировка", "category": "exclusion"},
    )

    resp = await api_client.get(
        f"/api/search-profiles/{test_search_profile_id}/keywords",
        params={"category": "exclusion"},
    )
    body = resp.json()
    assert len(body) == 1
    assert body[0]["category"] == "exclusion"


@pytest.mark.asyncio
async def test_update_and_delete_profile_keyword(api_client, test_search_profile_id):
    create_resp = await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/keywords",
        json={"text": "нужен сайт", "category": "direct_intent"},
    )
    keyword_id = create_resp.json()["id"]

    patch_resp = await api_client.patch(
        f"/api/search-profiles/{test_search_profile_id}/keywords/{keyword_id}",
        json={"enabled": False, "weight": 0.5},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["enabled"] is False
    assert patch_resp.json()["weight"] == 0.5

    delete_resp = await api_client.delete(
        f"/api/search-profiles/{test_search_profile_id}/keywords/{keyword_id}"
    )
    assert delete_resp.status_code == 204

    listed = await api_client.get(f"/api/search-profiles/{test_search_profile_id}/keywords")
    assert listed.json() == []


@pytest.mark.asyncio
async def test_keywords_404_for_foreign_profile(api_client):
    resp = await api_client.get("/api/search-profiles/9999/keywords")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cannot_update_another_profiles_keyword(api_client, api_db, test_search_profile_id):
    create_resp = await api_client.post(
        f"/api/search-profiles/{test_search_profile_id}/keywords",
        json={"text": "нужен сайт", "category": "direct_intent"},
    )
    keyword_id = create_resp.json()["id"]

    async with api_db() as session:
        from app.models.search_profile import SearchProfile
        from app.models.user import User

        other_user = User(email="other-kw@example.com", password_hash="x")
        session.add(other_user)
        await session.flush()
        other_profile = SearchProfile(user_id=other_user.id, name="Other")
        session.add(other_profile)
        await session.commit()
        other_profile_id = other_profile.id

    # keyword_id belongs to test_search_profile_id, not other_profile_id
    resp = await api_client.patch(
        f"/api/search-profiles/{other_profile_id}/keywords/{keyword_id}",
        json={"enabled": False},
    )
    assert resp.status_code == 404
