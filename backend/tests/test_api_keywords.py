"""Stage 9: /api/keywords REST endpoints."""
import pytest


@pytest.mark.asyncio
async def test_create_and_list_keywords(api_client):
    resp = await api_client.post(
        "/api/keywords", json={"keyword": "нужен сайт", "category": "direct_intent", "weight": 2.0}
    )
    assert resp.status_code == 201
    assert resp.json()["weight"] == 2.0

    resp = await api_client.get("/api/keywords")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_create_keyword_rejects_invalid_category(api_client):
    resp = await api_client.post("/api/keywords", json={"keyword": "x", "category": "not_a_category"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_duplicate_keyword_category_conflicts(api_client):
    payload = {"keyword": "нужен сайт", "category": "direct_intent"}
    resp1 = await api_client.post("/api/keywords", json=payload)
    assert resp1.status_code == 201

    resp2 = await api_client.post("/api/keywords", json=payload)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_list_keywords_filters_by_category(api_client):
    await api_client.post("/api/keywords", json={"keyword": "нужен сайт", "category": "direct_intent"})
    await api_client.post("/api/keywords", json={"keyword": "React", "category": "technology"})

    resp = await api_client.get("/api/keywords", params={"category": "technology"})
    keywords = resp.json()
    assert len(keywords) == 1
    assert keywords[0]["keyword"] == "React"


@pytest.mark.asyncio
async def test_update_keyword(api_client):
    resp = await api_client.post("/api/keywords", json={"keyword": "x", "category": "service"})
    kid = resp.json()["id"]

    resp = await api_client.patch(f"/api/keywords/{kid}", json={"is_active": False, "weight": 3.5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_active"] is False
    assert body["weight"] == 3.5


@pytest.mark.asyncio
async def test_delete_keyword(api_client):
    resp = await api_client.post("/api/keywords", json={"keyword": "x", "category": "service"})
    kid = resp.json()["id"]

    resp = await api_client.delete(f"/api/keywords/{kid}")
    assert resp.status_code == 204

    resp = await api_client.get("/api/keywords")
    assert resp.json() == []
