"""Stage 1 smoke test: the app boots and /health responds.

Uses an in-memory SQLite engine override so this test has zero external
dependencies (no Postgres required) — keeps the fast unit-test suite
runnable without Docker.
"""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok() -> None:
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "ReadHunter"
    assert body["database"] in {"ok", "error"}
