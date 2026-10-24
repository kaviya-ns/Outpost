import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.tables import Destination
from app.services.recertification import run_recertification_cycle
from tests.helpers import wait_for_job


@pytest.mark.asyncio
async def test_rules_propose_and_confirm(client):
    create = await client.post(
        "/api/v1/destinations",
        json={
            "name": "Rules Test Forum",
            "url": "https://forum.example.com",
            "platform_key": "discourse",
            "connector_key": "discourse",
            "connection": {},
        },
    )
    dest_id = create.json()["id"]

    resp = await client.post(f"/api/v1/destinations/{dest_id}/rules/propose")
    assert resp.status_code == 202
    job = await wait_for_job(client, resp.json()["job_id"])
    assert job["status"] == "succeeded"
    proposed = job["result"]["proposed_rules"]
    assert proposed["self_promo_allowed"] is False
    assert proposed["disclosure_required"] is True

    proposals = await client.get(f"/api/v1/destinations/{dest_id}/rules/proposals")
    proposal_id = proposals.json()[0]["id"]

    confirm = await client.post(
        f"/api/v1/destinations/{dest_id}/rules/proposals/{proposal_id}/confirm",
        json={"confirmed_by": "qa-reviewer", "accept": True},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"

    detail = await client.get("/api/v1/destinations")
    dest = next(d for d in detail.json() if d["id"] == dest_id)
    assert dest["disclosure_required"] is True


@pytest.mark.asyncio
async def test_tailoring_endpoint(client):
    dests = (await client.get("/api/v1/destinations")).json()
    discourse = next(d for d in dests if d["connector_key"] == "discourse")
    resp = await client.post(
        "/api/v1/tailor",
        json={
            "destination_id": discourse["id"],
            "rendition": {
                "title": "Shipping faster",
                "body": "We improved our pipeline.",
                "canonical_url": "https://example.com/post",
                "hashtags": ["ai", "saas"],
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rendition"]["title"].startswith("Thought:")
    assert "discussion_first_title" in data["warnings"]


@pytest.mark.asyncio
async def test_metrics_fetch_discourse(client):
    dests = (await client.get("/api/v1/destinations")).json()
    discourse = next(d for d in dests if d["connector_key"] == "discourse")
    pub = await client.post(
        "/connector/v1/discourse/publish",
        json={
            "rendition": {"title": "Metrics", "body": "body"},
            "destination": {"connector_key": "discourse", "instance_params": {"base_url": discourse["url"]}},
            "connection": {
                "credentials": {
                    "base_url": discourse["url"],
                    "api_key": "test-key",
                    "username": "system",
                }
            },
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    post_id = pub.json()["platform_post_id"]
    metrics = await client.get(
        "/api/v1/metrics",
        params={"destination_id": discourse["id"], "platform_post_id": post_id},
    )
    assert metrics.status_code == 200
    m = metrics.json()["metrics"]
    assert m["views"] >= 0
    assert "likes" in m and "comments" in m


@pytest.mark.asyncio
async def test_recertification_demotes_expired(client):
    dests = (await client.get("/api/v1/destinations")).json()
    discourse = next(d for d in dests if d["connector_key"] == "discourse")

    from app.db import SessionLocal

    async with SessionLocal() as db:
        result = await db.execute(select(Destination).where(Destination.id == discourse["id"]))
        dest = result.scalar_one()
        dest.certified = True
        dest.level = "L3"
        dest.publish_enabled = True
        dest.last_certified_at = datetime.now(timezone.utc) - timedelta(days=31)
        await db.commit()

    async with SessionLocal() as db:
        summary = await run_recertification_cycle(db)
        assert summary["demoted"] >= 1

    refreshed = (await client.get("/api/v1/destinations")).json()
    dest = next(d for d in refreshed if d["id"] == discourse["id"])
    assert dest["certified"] is False
    assert dest["level"] == "L0"

    alerts = await client.get("/api/v1/alerts/recertification")
    assert alerts.status_code == 200
    assert any(a["destination_id"] == discourse["id"] for a in alerts.json())
