"""Stage 9: /api/sources REST endpoints."""
import pytest


@pytest.mark.asyncio
async def test_create_and_list_sources(api_client):
    resp = await api_client.post(
        "/api/sources",
        json={"name": "Test Channel", "type": "telegram", "external_identifier": "test_channel"},
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "Test Channel"
    assert created["is_active"] is True

    resp = await api_client.get("/api/sources")
    assert resp.status_code == 200
    sources = resp.json()
    assert len(sources) == 1
    assert sources[0]["lead_count"] == 0


@pytest.mark.asyncio
async def test_create_source_rejects_invalid_type(api_client):
    resp = await api_client.post("/api/sources", json={"name": "X", "type": "carrier_pigeon"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_source_toggles_active(api_client):
    resp = await api_client.post("/api/sources", json={"name": "X", "type": "telegram"})
    source_id = resp.json()["id"]

    resp = await api_client.patch(f"/api/sources/{source_id}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_update_missing_source_404(api_client):
    resp = await api_client.patch("/api/sources/9999", json={"is_active": False})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_source(api_client):
    resp = await api_client.post("/api/sources", json={"name": "X", "type": "telegram"})
    source_id = resp.json()["id"]

    resp = await api_client.delete(f"/api/sources/{source_id}")
    assert resp.status_code == 204

    resp = await api_client.get("/api/sources")
    assert resp.json() == []


@pytest.mark.asyncio
async def test_delete_missing_source_404(api_client):
    resp = await api_client.delete("/api/sources/9999")
    assert resp.status_code == 404
