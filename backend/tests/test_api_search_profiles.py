"""Этап 4: /api/search-profiles CRUD (multi-profile) + /generate-draft."""
import pytest


@pytest.mark.asyncio
async def test_list_search_profiles_returns_all_owned(api_client, test_search_profile_id):
    resp = await api_client.get("/api/search-profiles")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == test_search_profile_id


@pytest.mark.asyncio
async def test_create_second_profile_for_same_user(api_client, test_search_profile_id):
    resp = await api_client.post(
        "/api/search-profiles", json={"name": "Второй поиск", "profession": "Веб-дизайнер"}
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Второй поиск"

    listed = await api_client.get("/api/search-profiles")
    assert len(listed.json()) == 2


@pytest.mark.asyncio
async def test_create_profile_seeds_global_keywords_when_none_provided(
    api_client, api_db, test_search_profile_id
):
    from app.repositories.keyword_repository import KeywordRepository
    from app.models.enums import KeywordCategory

    async with api_db() as session:
        await KeywordRepository(session).create(
            keyword="нужен сайт", category=KeywordCategory.DIRECT_INTENT.value, weight=2.0
        )
        await session.commit()

    resp = await api_client.post("/api/search-profiles", json={"name": "Новый поиск"})
    profile_id = resp.json()["id"]

    keywords_resp = await api_client.get(f"/api/search-profiles/{profile_id}/keywords")
    texts = {k["text"] for k in keywords_resp.json()}
    assert "нужен сайт" in texts


@pytest.mark.asyncio
async def test_create_profile_uses_provided_keywords_instead_of_global_seed(
    api_client, api_db
):
    from app.repositories.keyword_repository import KeywordRepository
    from app.models.enums import KeywordCategory

    async with api_db() as session:
        await KeywordRepository(session).create(
            keyword="глобальное слово, не должно попасть",
            category=KeywordCategory.DIRECT_INTENT.value,
            weight=1.0,
        )
        await session.commit()

    resp = await api_client.post(
        "/api/search-profiles",
        json={
            "name": "Онбординг поиск",
            "keywords": [
                {"text": "своё ключевое слово", "category": "direct_intent", "weight": 1.5}
            ],
        },
    )
    profile_id = resp.json()["id"]

    keywords_resp = await api_client.get(f"/api/search-profiles/{profile_id}/keywords")
    texts = {k["text"] for k in keywords_resp.json()}
    assert texts == {"своё ключевое слово"}


@pytest.mark.asyncio
async def test_generate_draft_returns_structured_profile(api_client):
    resp = await api_client.post(
        "/api/search-profiles/generate-draft",
        json={"description": "Я дизайнер карточек товаров для Wildberries и Ozon. Делаю инфографику."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["profession"]
    assert isinstance(body["suggested_keywords"], list)
    assert isinstance(body["suggested_exclusions"], list)
    assert "summary_direct" in body


@pytest.mark.asyncio
async def test_generate_draft_requires_auth(api_client, api_db):
    from app.core.security import get_current_user
    from app.main import app

    app.dependency_overrides.pop(get_current_user, None)

    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as unauth_client:
        resp = await unauth_client.post(
            "/api/search-profiles/generate-draft", json={"description": "x" * 20}
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_generate_draft_rejects_too_short_description(api_client):
    resp = await api_client.post(
        "/api/search-profiles/generate-draft", json={"description": "коротко"}
    )
    assert resp.status_code == 422
