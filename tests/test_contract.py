import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_connector_validate_assisted(client):
    r = await client.post(
        "/connector/v1/assisted/validate",
        json={
            "rendition": {"title": "T", "body": "B"},
            "destination": {"connector_key": "assisted", "name": "x"},
            "connection": {},
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_destinations_seeded(client):
    r = await client.get("/api/v1/destinations")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 6
