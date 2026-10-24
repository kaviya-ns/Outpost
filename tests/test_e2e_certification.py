import pytest

from tests.helpers import wait_for_job


@pytest.mark.asyncio
async def test_certify_all_core_destinations(client):
    dests = (await client.get("/api/v1/destinations")).json()
    assert len(dests) >= 6

    results = []
    for dest in dests:
        if dest["connector_key"] == "assisted":
            # Assisted uses pack flow; still runs full certify harness.
            pass
        resp = await client.post(f"/api/v1/destinations/{dest['id']}/certify")
        assert resp.status_code == 200
        job = await wait_for_job(client, resp.json()["job_id"])
        results.append(
            {
                "name": dest["name"],
                "connector_key": dest["connector_key"],
                "status": job["status"],
                "result": job.get("result"),
                "error": job.get("error"),
            }
        )
        assert job["status"] == "succeeded", results[-1]

    refreshed = (await client.get("/api/v1/destinations")).json()
    for dest in refreshed:
        if dest["connector_key"] in {"discourse", "lemmy", "devto", "ghost", "webhook_hmac", "assisted"}:
            assert dest["certified"] is True
            assert dest["level"] == "L3"
